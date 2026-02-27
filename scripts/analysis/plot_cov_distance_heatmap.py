#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from hydra import compose, initialize_config_dir
from hydra.core.global_hydra import GlobalHydra

from eapp.datasets.moabb_dataset import load_moabb_dataset
from eapp.eval.loso import (
    ProtocolConfig,
    _fit_ifsa_aligners_per_subject,
    _ifsa_cfg,
    _ifsa_reference_cov,
    _ifsa_target_mean_cov,
    _split_loso,
    _target_alignment_subset,
)
from eapp.representation.covariance import CovarianceConfig, compute_covariances
from eapp.utils.spd import invsqrtm_spd, log_euclidean_mean, logm_spd, sym

try:  # Optional dependency (may fail in restricted Python builds).
    import matplotlib.pyplot as plt  # type: ignore
except Exception:  # pragma: no cover
    plt = None

try:  # Optional dependency (may fail in restricted Python builds).
    import seaborn as sns  # type: ignore
except Exception:  # pragma: no cover
    sns = None


def _compose_cfg(overrides: list[str]) -> object:
    repo_root = Path(__file__).resolve().parents[2]
    config_dir = (repo_root / "configs").as_posix()
    if GlobalHydra.instance().is_initialized():
        GlobalHydra.instance().clear()
    with initialize_config_dir(version_base=None, config_dir=config_dir):
        return compose(config_name="config", overrides=overrides)


def _airm_distance(a: np.ndarray, b: np.ndarray, eps: float) -> float:
    d = invsqrtm_spd(sym(a), eps=eps)
    delta = logm_spd(sym(d @ b @ d), eps=eps)
    return float(np.linalg.norm(delta, ord="fro"))


def _mean_cov_logeuclid(covs: np.ndarray, eps: float) -> np.ndarray:
    if covs.shape[0] == 0:
        raise ValueError("empty covs")
    return log_euclidean_mean(covs, eps=eps)


def _subject_mean_covs(
    x: np.ndarray,
    meta: pd.DataFrame,
    cov_cfg: CovarianceConfig,
) -> dict[int, np.ndarray]:
    covs = compute_covariances(x, cov_cfg)
    subjects = meta["subject"].to_numpy()
    out: dict[int, np.ndarray] = {}
    for s in sorted(set(subjects.tolist())):
        covs_s = covs[subjects == s]
        if covs_s.shape[0] == 0:
            continue
        out[int(s)] = _mean_cov_logeuclid(covs_s, eps=cov_cfg.epsilon)
    return out


def _plot_heatmap(dist: np.ndarray, labels: list[str], out_path: Path, title: str) -> None:
    if plt is None or sns is None:
        return
    plt.figure(figsize=(6.5, 5.5))
    sns.heatmap(dist, xticklabels=labels, yticklabels=labels, cmap="viridis", square=True)
    plt.title(title)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=180)
    plt.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Covariance AIRM distance heatmaps (before/EA/IFSA) for one LOSO fold."
        )
    )
    parser.add_argument("--dataset", default="bci_iv_2a")
    parser.add_argument(
        "--target-data-usage",
        default="transductive_unlabeled_all",
        choices=["transductive_unlabeled_all", "online_prefix_unlabeled"],
    )
    parser.add_argument("--target-subject", type=int, default=9)
    parser.add_argument("--ifsa-experiment", default="ifsa_final_v1")
    parser.add_argument("--results-dir", default="results")
    args = parser.parse_args(argv)

    overrides = [
        f"dataset={args.dataset}",
        f"protocol.target_data_usage={args.target_data_usage}",
        f"experiment={args.ifsa_experiment}",
        "runtime.n_jobs=1",
    ]
    cfg = _compose_cfg(overrides)

    runtime = cfg.runtime
    bundle = load_moabb_dataset(
        moabb_class=str(cfg.dataset.moabb_class),
        events=list(cfg.dataset.events),
        subjects=list(cfg.dataset.subjects) if cfg.dataset.subjects is not None else None,
        fmin=float(cfg.preprocess.fmin),
        fmax=float(cfg.preprocess.fmax),
        tmin=float(cfg.preprocess.tmin),
        tmax=float(cfg.preprocess.tmax),
        resample=float(cfg.preprocess.resample) if cfg.preprocess.resample is not None else None,
        drop_eog=bool(cfg.preprocess.drop_eog),
        scale=float(getattr(cfg.preprocess, "scale", 1.0)),
        cache_dir=Path(str(runtime.cache_dir)),
    )

    cov_cfg = CovarianceConfig(
        estimator=str(cfg.preprocess.covariance.estimator),
        epsilon=float(cfg.preprocess.covariance.epsilon),
    )
    protocol = ProtocolConfig(
        target_data_usage=str(cfg.protocol.target_data_usage),
        online_prefix_n_trials=int(cfg.protocol.online_prefix_n_trials),
        few_shot_n_trials=int(cfg.protocol.few_shot_n_trials),
    )
    folds = _split_loso(bundle.meta)
    fold = next((f for f in folds if int(f[0]) == int(args.target_subject)), None)
    if fold is None:
        raise SystemExit(
            f"target_subject={args.target_subject} not found in dataset={args.dataset}"
        )
    target_subject, train_idx, test_idx = fold

    x_train = bundle.x[train_idx]
    meta_train = bundle.meta.iloc[train_idx]
    x_test = bundle.x[test_idx]
    meta_test = bundle.meta.iloc[test_idx]

    # ---------- BEFORE ----------
    before_means = _subject_mean_covs(
        np.concatenate([x_train, x_test], axis=0),
        pd.concat([meta_train, meta_test], ignore_index=True),
        cov_cfg,
    )

    # ---------- EA (per-subject whitening to I; target uses protocol subset for fit) ----------
    from eapp.alignment.ea import EASignalAligner

    ea_means: dict[int, np.ndarray] = {}
    subjects_train = meta_train["subject"].to_numpy()
    x_train_ea = np.empty_like(x_train)
    for s in np.unique(subjects_train):
        mask = subjects_train == s
        x_s = x_train[mask]
        if x_s.shape[0] == 0:
            continue
        x_train_ea[mask] = EASignalAligner(cov_cfg).fit(x_s).transform(x_s)

    x_fit = _target_alignment_subset(x_test, protocol)
    x_test_ea = EASignalAligner(cov_cfg).fit(x_fit).transform(x_test)

    ea_means.update(_subject_mean_covs(x_train_ea, meta_train, cov_cfg))
    ea_means[target_subject] = _subject_mean_covs(x_test_ea, meta_test, cov_cfg)[target_subject]

    # ---------- IFSA-final ----------
    # target-guided; source aligned to target desired; target stays identity.
    method_cfg = dict(cfg.method)
    cfg_ifsa = _ifsa_cfg(method_cfg)
    ref = _ifsa_reference_cov(x_train, meta_train, cov_cfg, method_cfg)

    x_fit = _target_alignment_subset(x_test, protocol)
    covs_fit = compute_covariances(x_fit, cov_cfg)
    target_mean_cov = _ifsa_target_mean_cov(x_fit, cov_cfg, cfg_ifsa, covs=covs_fit)

    x_train_ifsa, _ = _fit_ifsa_aligners_per_subject(
        x_train,
        meta_train,
        cov_cfg,
        method_cfg,
        ref,
        target_mean_cov=target_mean_cov,
        target_dispersion=None,
    )

    ifsa_means = _subject_mean_covs(x_train_ifsa, meta_train, cov_cfg)
    ifsa_means[target_subject] = _subject_mean_covs(x_test, meta_test, cov_cfg)[target_subject]

    def _dist_matrix(means: dict[int, np.ndarray]) -> tuple[np.ndarray, list[str]]:
        subs = sorted(means.keys())
        mats = [means[s] for s in subs]
        n = len(mats)
        d = np.zeros((n, n), dtype=float)
        for i in range(n):
            for j in range(n):
                d[i, j] = _airm_distance(mats[i], mats[j], eps=cov_cfg.epsilon)
        labels = [str(s) for s in subs]
        return d, labels

    out_dir = Path(args.results_dir) / "figures" / "paper"
    d0, labels0 = _dist_matrix(before_means)
    d1, labels1 = _dist_matrix(ea_means)
    d2, labels2 = _dist_matrix(ifsa_means)

    tag = f"{args.dataset}__{args.target_data_usage}__target{target_subject}"
    _plot_heatmap(d0, labels0, out_dir / f"cov_heatmap__before__{tag}.png", f"Before ({tag})")
    _plot_heatmap(d1, labels1, out_dir / f"cov_heatmap__ea__{tag}.png", f"EA ({tag})")
    _plot_heatmap(
        d2,
        labels2,
        out_dir / f"cov_heatmap__ifsa__{tag}.png",
        f"IFSA ({args.ifsa_experiment}) ({tag})",
    )

    print("[done] heatmaps written under:", out_dir)


if __name__ == "__main__":
    main()
