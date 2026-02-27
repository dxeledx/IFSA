#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from hydra import compose, initialize_config_dir
from hydra.core.global_hydra import GlobalHydra
from sklearn.manifold import TSNE

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
from eapp.utils.spd import logm_spd, sym

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


def _vec_upper_tri(m: np.ndarray) -> np.ndarray:
    idx = np.triu_indices(m.shape[0])
    return m[idx]


def _cov_features(covs: np.ndarray, eps: float) -> np.ndarray:
    feats = np.empty((covs.shape[0], covs.shape[1] * (covs.shape[1] + 1) // 2), dtype=float)
    for i, cov in enumerate(covs):
        logm = logm_spd(sym(cov), eps=eps)
        feats[i] = _vec_upper_tri(logm)
    return feats


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="t-SNE of trial covariances for one LOSO fold (before/EA/IFSA)."
    )
    parser.add_argument("--dataset", default="bci_iv_2a")
    parser.add_argument(
        "--target-data-usage",
        default="transductive_unlabeled_all",
        choices=["transductive_unlabeled_all", "online_prefix_unlabeled"],
    )
    parser.add_argument("--target-subject", type=int, default=9)
    parser.add_argument("--ifsa-experiment", default="ifsa_final_v1")
    parser.add_argument("--max-trials", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=0)
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
    y_train = bundle.y[train_idx]
    meta_train = bundle.meta.iloc[train_idx].copy()
    x_test = bundle.x[test_idx]
    y_test = bundle.y[test_idx]
    meta_test = bundle.meta.iloc[test_idx].copy()

    # Label domain for plotting.
    meta_train["domain"] = "source"
    meta_test["domain"] = "target"

    # ---------- BEFORE ----------
    x_before = np.concatenate([x_train, x_test], axis=0)
    y_before = np.concatenate([y_train, y_test], axis=0)
    meta_before = pd.concat([meta_train, meta_test], ignore_index=True)

    # ---------- EA ----------
    from eapp.alignment.ea import EASignalAligner

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
    x_ea = np.concatenate([x_train_ea, x_test_ea], axis=0)

    # ---------- IFSA ----------
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
    x_ifsa = np.concatenate([x_train_ifsa, x_test], axis=0)  # target identity

    def _stack_features(x_sig: np.ndarray) -> np.ndarray:
        covs = compute_covariances(x_sig, cov_cfg)
        return _cov_features(covs, eps=cov_cfg.epsilon)

    feats_before = _stack_features(x_before)
    feats_ea = _stack_features(x_ea)
    feats_ifsa = _stack_features(x_ifsa)

    # Subsample for speed.
    rng = np.random.default_rng(int(args.seed))
    n = int(min(args.max_trials, feats_before.shape[0]))
    idx = rng.choice(feats_before.shape[0], size=n, replace=False)

    def _embed(feats: np.ndarray) -> np.ndarray:
        tsne = TSNE(
            n_components=2,
            init="pca",
            learning_rate="auto",
            perplexity=min(30.0, max(5.0, (n - 1) / 10.0)),
            random_state=int(args.seed),
        )
        return tsne.fit_transform(feats[idx])

    emb0 = _embed(feats_before)
    emb1 = _embed(feats_ea)
    emb2 = _embed(feats_ifsa)

    df_plot = meta_before.iloc[idx].copy()
    df_plot["y"] = y_before[idx].astype(int)

    out_dir = Path(args.results_dir) / "figures" / "paper"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{args.dataset}__{args.target_data_usage}__target{target_subject}"

    def _plot(emb: np.ndarray, title: str, out_path: Path) -> None:
        if plt is None or sns is None:
            return
        df = df_plot.copy()
        df["x0"] = emb[:, 0]
        df["x1"] = emb[:, 1]
        plt.figure(figsize=(7.0, 5.2))
        sns.scatterplot(
            data=df,
            x="x0",
            y="x1",
            hue="subject",
            style="y",
            palette="tab10",
            alpha=0.75,
            s=35,
        )
        plt.title(title)
        plt.legend(bbox_to_anchor=(1.02, 1), loc="upper left", borderaxespad=0.0)
        plt.tight_layout()
        plt.savefig(out_path, dpi=180)
        plt.close()

    _plot(emb0, f"Before (t-SNE) ({tag})", out_dir / f"tsne__before__{tag}.png")
    _plot(emb1, f"EA (t-SNE) ({tag})", out_dir / f"tsne__ea__{tag}.png")
    _plot(
        emb2,
        f"IFSA ({args.ifsa_experiment}) (t-SNE) ({tag})",
        out_dir / f"tsne__ifsa__{tag}.png",
    )

    print("[done] tsne figures written under:", out_dir)


if __name__ == "__main__":
    main()
