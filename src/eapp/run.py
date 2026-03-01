from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd
from hydra import compose, initialize_config_dir
from hydra.core.global_hydra import GlobalHydra
from omegaconf import OmegaConf

from eapp.alignment.ea_pp import EAPPConfig, EAPPSignalAligner
from eapp.datasets.moabb_dataset import load_moabb_dataset
from eapp.eval.loso import ProtocolConfig, run_loso
from eapp.eval.plots import (
    plot_baseline_vs_method,
    plot_log_eig_violin,
    plot_paired_subject_lines,
)
from eapp.representation.covariance import CovarianceConfig, compute_covariances
from eapp.utils.spd import log_eigvals_spd


def _git_hash(repo_root: Path) -> str | None:
    # If this project folder isn't a git repo, avoid returning an unrelated
    # parent-repo hash (e.g. when the user's home directory is a git repo).
    if not (repo_root / ".git").exists():
        return None
    try:
        return (
            subprocess.check_output(
                ["git", "-C", repo_root.as_posix(), "rev-parse", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return None


def _pip_freeze() -> list[str] | None:
    try:
        out = subprocess.check_output([os.environ.get("PYTHON", "python"), "-m", "pip", "freeze"])
        return out.decode().splitlines()
    except Exception:
        return None


def _sha256_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _code_manifest(repo_root: Path) -> tuple[list[dict], str]:
    files: list[Path] = []

    for pattern in [
        "src/**/*.py",
        "configs/**/*.yaml",
        "scripts/**/*.sh",
    ]:
        files.extend(repo_root.glob(pattern))

    for rel in [
        "requirements.txt",
        "requirements-dev.txt",
        "pyproject.toml",
        "README.md",
        ".gitignore",
        "codex.remote.toml",
    ]:
        p = repo_root / rel
        if p.exists():
            files.append(p)

    unique = {p.resolve() for p in files if p.is_file()}
    manifest = []
    for p in sorted(unique, key=lambda x: x.as_posix()):
        rel = p.relative_to(repo_root).as_posix()
        manifest.append({"path": rel, "sha256": _sha256_file(p), "size": int(p.stat().st_size)})

    snapshot_in = "\n".join(f"{m['path']}\t{m['sha256']}\t{m['size']}" for m in manifest).encode(
        "utf-8"
    )
    snapshot = sha256(snapshot_in).hexdigest()
    return manifest, snapshot


def _env_info(*, capture_pip: bool, repo_root: Path) -> dict:
    info = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "git_hash": _git_hash(repo_root),
    }
    if capture_pip:
        info["pip_freeze"] = _pip_freeze()

    manifest, snapshot = _code_manifest(repo_root)
    info["code_manifest"] = manifest
    info["code_snapshot_sha256"] = snapshot
    return info


def _seed_everything(seed: int) -> None:
    np.random.seed(seed)


def _collect_eapp_logeig(
    x: np.ndarray,
    meta: pd.DataFrame,
    cov_cfg: CovarianceConfig,
    method_cfg: dict,
) -> pd.DataFrame:
    rows = []
    subjects = meta["subject"].to_numpy()
    for s in np.unique(subjects):
        x_s = x[subjects == s]
        if x_s.shape[0] == 0:
            continue

        # Keep it cheap by sampling only a prefix.
        x_s = x_s[: min(50, x_s.shape[0])]

        cfg = EAPPConfig(
            lambda_mean=float(method_cfg["lambda_mean"]),
            lambda_spec=float(method_cfg["lambda_spec"]),
            lambda_u=float(method_cfg["lambda_u"]),
            k_steps=int(method_cfg["k_steps"]),
            lr=float(method_cfg["lr"]),
            ema_alpha=float(method_cfg["ema_alpha"]),
        )
        aligner = EAPPSignalAligner(cov_cfg, cfg).fit(x_s)
        covs = compute_covariances(x_s, cov_cfg)

        for cov in covs:
            for val in log_eigvals_spd(cov, cov_cfg.epsilon):
                rows.append({"stage": "before", "log_eig": float(val)})

        a = aligner.matrix
        assert a is not None
        for cov in covs:
            cov_a = a @ cov @ a.T
            for val in log_eigvals_spd(cov_a, cov_cfg.epsilon):
                rows.append({"stage": "after", "log_eig": float(val)})

    return pd.DataFrame(rows)


def _compose_cfg(overrides: list[str]) -> object:
    config_dir = (Path(__file__).resolve().parents[2] / "configs").as_posix()
    if GlobalHydra.instance().is_initialized():
        GlobalHydra.instance().clear()
    with initialize_config_dir(version_base=None, config_dir=config_dir):
        return compose(config_name="config", overrides=overrides)


def main(argv: list[str] | None = None) -> None:
    overrides = sys.argv[1:] if argv is None else argv
    cfg = _compose_cfg(overrides)

    ts = datetime.now().strftime("%Y-%m-%d/%H-%M-%S")
    run_dir = Path("runs") / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "config.yaml").write_text(OmegaConf.to_yaml(cfg), encoding="utf-8")

    runtime = cfg.runtime
    _seed_everything(int(runtime.seed))

    repo_root = Path(__file__).resolve().parents[2]
    env_path = run_dir / "env.json"
    env_path.write_text(
        json.dumps(
            _env_info(capture_pip=bool(runtime.capture_env), repo_root=repo_root),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

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

    protocol_cfg = ProtocolConfig(
        target_data_usage=str(cfg.protocol.target_data_usage),
        online_prefix_n_trials=int(cfg.protocol.online_prefix_n_trials),
        few_shot_n_trials=int(cfg.protocol.few_shot_n_trials),
    )

    df = run_loso(
        x=bundle.x,
        y=bundle.y,
        meta=bundle.meta,
        classes=bundle.classes,
        protocol_cfg=protocol_cfg,
        method_name=str(cfg.method.name),
        method_cfg=OmegaConf.to_container(cfg.method, resolve=True),
        model_name=str(cfg.model.name),
        model_cfg=OmegaConf.to_container(cfg.model, resolve=True),
        cov_cfg=cov_cfg,
        compute_baseline=bool(cfg.eval.compute_baseline),
        baseline_method=str(cfg.eval.baseline_method),
        n_jobs=int(runtime.n_jobs),
        subject_n_jobs=int(getattr(cfg.eval, "subject_n_jobs", 1)),
        trim_memory=bool(getattr(cfg.eval, "trim_memory", False)),
    )

    df.insert(0, "dataset", str(cfg.dataset.name))
    df.insert(1, "method", str(cfg.method.name))
    variant = getattr(cfg, "experiment_name", None) or str(cfg.method.name)
    df.insert(2, "variant", variant)
    df.insert(3, "model", str(cfg.model.name))
    df.insert(4, "target_data_usage", str(cfg.protocol.target_data_usage))

    results_dir = Path(str(runtime.results_dir))
    tables_dir = results_dir / "tables"
    figs_dir = results_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figs_dir.mkdir(parents=True, exist_ok=True)

    tag = f"{cfg.dataset.name}__{variant}__{cfg.model.name}__{cfg.protocol.target_data_usage}"
    csv_path = tables_dir / f"{tag}.csv"
    df.to_csv(csv_path, index=False)

    plot_baseline_vs_method(df, figs_dir / f"{tag}__bar.png")
    plot_paired_subject_lines(df, figs_dir / f"{tag}__paired.png")
    if str(cfg.method.name) == "ea_pp":
        df_logeig = _collect_eapp_logeig(
            bundle.x, bundle.meta, cov_cfg, OmegaConf.to_container(cfg.method, resolve=True)
        )
        plot_log_eig_violin(df_logeig, figs_dir / f"{tag}__spectrum.png")

    print(f"[done] results: {csv_path}")


if __name__ == "__main__":
    main()
