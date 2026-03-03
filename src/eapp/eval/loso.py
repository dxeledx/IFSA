from __future__ import annotations

import gc
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from eapp.alignment.coral import CoralSignalAligner, coral_matrix
from eapp.alignment.ea import EASignalAligner
from eapp.alignment.identity import IdentitySignalAligner
from eapp.alignment.ifsa import IFSAConfig, IFSASignalAligner
from eapp.alignment.ra import RASignalAligner
from eapp.alignment.tsa import TSAConfig, align_tangent_space
from eapp.alignment.tsa_ss import TSASSConfig, align_tangent_space_with_stable_subspace
from eapp.eval.metrics import compute_metrics
from eapp.eval.stats import paired_wilcoxon_with_effect
from eapp.representation.covariance import CovarianceConfig, compute_covariances
from eapp.utils.spd import (
    clamp_eigenvalues,
    eigh_sym,
    expm_sym,
    invsqrtm_spd,
    log_euclidean_mean,
    logm_spd,
    sym,
)


@dataclass(frozen=True)
class ProtocolConfig:
    target_data_usage: str
    online_prefix_n_trials: int
    few_shot_n_trials: int


def _trim_memory() -> None:
    """Best-effort memory trim to reduce RSS growth on large runs.

    - `gc.collect()` clears reference cycles promptly.
    - On glibc (Linux), `malloc_trim(0)` may return freed heap pages to the OS.
    """

    gc.collect()
    try:
        import ctypes
        import ctypes.util

        libc_name = ctypes.util.find_library("c")
        if not libc_name:
            return
        libc = ctypes.CDLL(libc_name)
        trim = getattr(libc, "malloc_trim", None)
        if trim is None:
            return
        trim(0)
    except Exception:
        # Never fail evaluation due to trimming.
        return


def _split_loso(meta: pd.DataFrame) -> list[tuple[int, np.ndarray, np.ndarray]]:
    subjects = np.asarray(sorted(meta["subject"].unique().tolist()))
    folds = []
    for target_subject in subjects:
        test_mask = meta["subject"].to_numpy() == target_subject
        train_idx = np.where(~test_mask)[0]
        test_idx = np.where(test_mask)[0]
        folds.append((int(target_subject), train_idx, test_idx))
    return folds


def _target_alignment_subset(x_target: np.ndarray, protocol: ProtocolConfig) -> np.ndarray:
    if protocol.target_data_usage == "transductive_unlabeled_all":
        return x_target
    if protocol.target_data_usage == "online_prefix_unlabeled":
        n = int(min(protocol.online_prefix_n_trials, x_target.shape[0]))
        return x_target[:n]
    if protocol.target_data_usage == "few_shot_labeled":
        n = int(min(protocol.few_shot_n_trials, x_target.shape[0]))
        return x_target[:n]
    raise ValueError(f"Unknown protocol.target_data_usage={protocol.target_data_usage}")


def _metrics_to_extra(metrics: object | None) -> dict:
    if metrics is None:
        return {}
    try:
        items = vars(metrics).items()
    except TypeError:
        return {}

    out: dict[str, float | int] = {}
    for key, val in items:
        if isinstance(val, (np.floating, np.integer)):
            val = val.item()
        if isinstance(val, bool):
            out[key] = int(val)
        elif isinstance(val, (int, float)):
            out[key] = val
    return out


def _ifsa_cfg(method_cfg: dict) -> IFSAConfig:
    return IFSAConfig(
        lambda_track=float(method_cfg["lambda_track"]),
        lambda_spec=float(method_cfg["lambda_spec"]),
        lambda_damp=float(method_cfg["lambda_damp"]),
        cov_trace_norm=bool(method_cfg.get("cov_trace_norm", False)),
        cov_shrink_alpha=float(method_cfg.get("cov_shrink_alpha", 0.0)),
        cov_log_spec_shrink=float(method_cfg.get("cov_log_spec_shrink", 0.0)),
        mean_mode=str(method_cfg.get("mean_mode", "arith")),
        target_beta=float(method_cfg.get("target_beta", 0.0)),
        desired_shrink_alpha=float(method_cfg.get("desired_shrink_alpha", 0.0)),
        desired_log_spec_shrink=float(method_cfg.get("desired_log_spec_shrink", 0.0)),
        lambda_u=float(method_cfg["lambda_u"]),
        k_steps=int(method_cfg["k_steps"]),
        lr=float(method_cfg["lr"]),
        ema_alpha=float(method_cfg["ema_alpha"]),
        thrust_mode=str(method_cfg.get("thrust_mode", "spd")),
        a_mix_mode=str(method_cfg.get("a_mix_mode", "euclid")),
        lambda_disp=float(method_cfg.get("lambda_disp", 0.0)),
        disp_scale_min=float(method_cfg.get("disp_scale_min", 0.5)),
        disp_scale_max=float(method_cfg.get("disp_scale_max", 2.0)),
        trigger_tau=float(method_cfg["trigger_tau"]),
        trigger_mode=str(method_cfg.get("trigger_mode", "fixed")),
        trigger_quantile=float(method_cfg.get("trigger_quantile", 0.7)),
        damp_mode=str(method_cfg.get("damp_mode", "euclid_ema")),
        output_space=str(method_cfg.get("output_space", "reference")),
        ref_subject_mean_mode=str(method_cfg.get("ref_subject_mean_mode", "arith")),
    )


def _ifsa_reference_cov(
    x: np.ndarray, meta: pd.DataFrame, cov_cfg: CovarianceConfig, method_cfg: dict
) -> np.ndarray:
    """Estimate IFSA inertial reference R_* from source subjects only (no target leakage)."""

    cfg = _ifsa_cfg(method_cfg)
    subjects = meta["subject"].to_numpy()
    covs_all = compute_covariances(x, cov_cfg)

    def _trace_norm(covs: np.ndarray) -> np.ndarray:
        if covs.shape[0] == 0 or not cfg.cov_trace_norm:
            return covs
        dim = covs.shape[1]
        out = np.empty_like(covs)
        for i, cov in enumerate(covs):
            t = float(np.trace(cov)) / float(dim)
            t = max(float(cov_cfg.epsilon), t)
            out[i] = sym(cov / t)
        return out

    def _trace_shrink(covs: np.ndarray, alpha: float) -> np.ndarray:
        alpha = float(alpha)
        if covs.shape[0] == 0 or alpha <= 0.0:
            return covs
        alpha = max(0.0, min(0.3, alpha))
        dim = covs.shape[1]
        eye = np.eye(dim, dtype=float)
        out = np.empty_like(covs)
        for i, cov in enumerate(covs):
            t = float(np.trace(cov)) / float(dim)
            out[i] = sym((1.0 - alpha) * cov + alpha * t * eye)
        return out

    def _log_spec_shrink(covs: np.ndarray) -> np.ndarray:
        strength = max(0.0, min(1.0, float(cfg.cov_log_spec_shrink)))
        if covs.shape[0] == 0 or strength <= 0.0:
            return covs
        out = np.empty_like(covs)
        for i, cov in enumerate(covs):
            decomp = eigh_sym(cov)
            values = clamp_eigenvalues(decomp.values, 1e-30)
            log_vals = np.log(values)
            mean_log = float(np.mean(log_vals))
            log_new = mean_log + (1.0 - strength) * (log_vals - mean_log)
            out[i] = sym(decomp.vectors @ np.diag(np.exp(log_new)) @ decomp.vectors.T)
        return out

    def _ema_euclid(covs: np.ndarray, rho: float) -> np.ndarray:
        if covs.shape[0] <= 1 or rho <= 0.0:
            return covs
        out = np.empty_like(covs)
        out[0] = covs[0]
        for i in range(1, covs.shape[0]):
            out[i] = sym((1.0 - rho) * out[i - 1] + rho * covs[i])
        return out

    def _ema_log(covs: np.ndarray, rho: float, eps: float) -> np.ndarray:
        if covs.shape[0] <= 1 or rho <= 0.0:
            return covs
        out = np.empty_like(covs)
        prev = logm_spd(covs[0], eps=eps)
        out[0] = covs[0]
        for i in range(1, covs.shape[0]):
            cur = logm_spd(covs[i], eps=eps)
            prev = sym((1.0 - rho) * prev + rho * cur)
            out[i] = expm_sym(prev)
        return out

    def _smooth(covs: np.ndarray) -> np.ndarray:
        covs = _trace_norm(covs)
        covs = _trace_shrink(covs, cfg.cov_shrink_alpha)
        covs = _log_spec_shrink(covs)
        rho = max(0.0, min(0.99, float(cfg.lr) * float(cfg.lambda_damp)))
        if cfg.damp_mode == "euclid_ema":
            return _ema_euclid(covs, rho=rho)
        if cfg.damp_mode == "log_ema":
            return _ema_log(covs, rho=rho, eps=cov_cfg.epsilon)
        raise ValueError(f"Unknown IFSA damp_mode={cfg.damp_mode!r}")

    def _mean_cov(covs: np.ndarray, mode: str) -> np.ndarray:
        if mode == "arith":
            return sym(np.mean(covs, axis=0))
        if mode == "logeuclid":
            return log_euclidean_mean(covs, eps=cov_cfg.epsilon)
        raise ValueError(f"Unknown IFSA ref_subject_mean_mode={mode!r}")

    means = []
    for s in np.unique(subjects):
        mask = subjects == s
        covs_s = covs_all[mask]
        if covs_s.shape[0] == 0:
            continue
        covs_s = _smooth(covs_s)
        means.append(_mean_cov(covs_s, mode=str(cfg.ref_subject_mean_mode)))

    if not means:
        raise RuntimeError("Failed to compute IFSA reference covariance (no subject covariances)")
    return log_euclidean_mean(np.stack(means, axis=0), eps=cov_cfg.epsilon)


def _ifsa_track_error_before_from_covs(
    covs: np.ndarray, cfg: IFSAConfig, reference_cov: np.ndarray, eps: float
) -> float:
    """Compute IFSA tracking error e(I) from covariances (no fitting / no labels)."""
    if covs.shape[0] == 0:
        raise ValueError("covs must be non-empty")

    if cfg.cov_trace_norm:
        dim = covs.shape[1]
        covs = np.stack(
            [sym(cov / max(float(eps), float(np.trace(cov)) / float(dim))) for cov in covs],
            axis=0,
        )

    alpha = max(0.0, min(0.3, float(cfg.cov_shrink_alpha)))
    if alpha > 0.0:
        dim = covs.shape[1]
        eye = np.eye(dim, dtype=float)
        covs = np.stack(
            [sym((1.0 - alpha) * cov + alpha * (float(np.trace(cov)) / dim) * eye) for cov in covs],
            axis=0,
        )

    strength = max(0.0, min(1.0, float(cfg.cov_log_spec_shrink)))
    if strength > 0.0:
        out = np.empty_like(covs)
        for i, cov in enumerate(covs):
            decomp = eigh_sym(cov)
            values = clamp_eigenvalues(decomp.values, 1e-30)
            log_vals = np.log(values)
            mean_log = float(np.mean(log_vals))
            log_new = mean_log + (1.0 - strength) * (log_vals - mean_log)
            out[i] = sym(decomp.vectors @ np.diag(np.exp(log_new)) @ decomp.vectors.T)
        covs = out

    rho = max(0.0, min(0.99, float(cfg.lr) * float(cfg.lambda_damp)))
    if cfg.damp_mode == "euclid_ema":
        covs_smooth = covs
        if covs.shape[0] > 1 and rho > 0.0:
            out = np.empty_like(covs)
            out[0] = covs[0]
            for i in range(1, covs.shape[0]):
                out[i] = sym((1.0 - rho) * out[i - 1] + rho * covs[i])
            covs_smooth = out
    elif cfg.damp_mode == "log_ema":
        covs_smooth = covs
        if covs.shape[0] > 1 and rho > 0.0:
            out = np.empty_like(covs)
            prev = logm_spd(covs[0], eps=eps)
            out[0] = covs[0]
            for i in range(1, covs.shape[0]):
                cur = logm_spd(covs[i], eps=eps)
                prev = sym((1.0 - rho) * prev + rho * cur)
                out[i] = expm_sym(prev)
            covs_smooth = out
    else:
        raise ValueError(f"Unknown IFSA damp_mode={cfg.damp_mode!r}")

    w = invsqrtm_spd(sym(reference_cov), eps=eps)
    cov_w = np.einsum("ij,njk,lk->nil", w, covs_smooth, w)
    if cfg.mean_mode == "arith":
        mean_white = sym(np.mean(cov_w, axis=0))
    elif cfg.mean_mode == "logeuclid":
        mean_white = log_euclidean_mean(cov_w, eps=eps)
    else:
        raise ValueError(f"Unknown IFSA mean_mode={cfg.mean_mode!r}")

    error0 = logm_spd(mean_white, eps=eps)
    return float(np.linalg.norm(error0, ord="fro"))


def _ifsa_target_mean_cov(
    x: np.ndarray,
    cov_cfg: CovarianceConfig,
    cfg: IFSAConfig,
    *,
    covs: np.ndarray | None = None,
) -> np.ndarray:
    """Compute target mean covariance for target-guided IFSA (unlabeled)."""

    if covs is None:
        covs = compute_covariances(x, cov_cfg)
    if covs.shape[0] == 0:
        raise ValueError("Target alignment subset is empty")

    if cfg.cov_trace_norm:
        dim = covs.shape[1]
        covs = np.stack(
            [
                sym(
                    cov
                    / max(float(cov_cfg.epsilon), float(np.trace(cov)) / float(dim))
                )
                for cov in covs
            ],
            axis=0,
        )

    alpha = max(0.0, min(0.3, float(cfg.cov_shrink_alpha)))
    if alpha > 0.0:
        dim = covs.shape[1]
        eye = np.eye(dim, dtype=float)
        covs = np.stack(
            [sym((1.0 - alpha) * cov + alpha * (float(np.trace(cov)) / dim) * eye) for cov in covs],
            axis=0,
        )

    strength = max(0.0, min(1.0, float(cfg.cov_log_spec_shrink)))
    if strength > 0.0:
        out = np.empty_like(covs)
        for i, cov in enumerate(covs):
            decomp = eigh_sym(cov)
            values = clamp_eigenvalues(decomp.values, 1e-30)
            log_vals = np.log(values)
            mean_log = float(np.mean(log_vals))
            log_new = mean_log + (1.0 - strength) * (log_vals - mean_log)
            out[i] = sym(decomp.vectors @ np.diag(np.exp(log_new)) @ decomp.vectors.T)
        covs = out

    rho = max(0.0, min(0.99, float(cfg.lr) * float(cfg.lambda_damp)))
    if cfg.damp_mode == "euclid_ema":
        if covs.shape[0] > 1 and rho > 0.0:
            out = np.empty_like(covs)
            out[0] = covs[0]
            for i in range(1, covs.shape[0]):
                out[i] = sym((1.0 - rho) * out[i - 1] + rho * covs[i])
            covs = out
    elif cfg.damp_mode == "log_ema":
        if covs.shape[0] > 1 and rho > 0.0:
            out = np.empty_like(covs)
            prev = logm_spd(covs[0], eps=cov_cfg.epsilon)
            out[0] = covs[0]
            for i in range(1, covs.shape[0]):
                cur = logm_spd(covs[i], eps=cov_cfg.epsilon)
                prev = sym((1.0 - rho) * prev + rho * cur)
                out[i] = expm_sym(prev)
            covs = out
    else:
        raise ValueError(f"Unknown IFSA damp_mode={cfg.damp_mode!r}")

    if cfg.mean_mode == "arith":
        return sym(np.mean(covs, axis=0))
    if cfg.mean_mode == "logeuclid":
        return log_euclidean_mean(covs, eps=cov_cfg.epsilon)
    raise ValueError(f"Unknown IFSA mean_mode={cfg.mean_mode!r}")


def _ifsa_split_half_stability_score_from_covs(
    covs: np.ndarray,
    cov_cfg: CovarianceConfig,
    cfg: IFSAConfig,
) -> float:
    """Split-half stability score for target-guided safety clutch (unlabeled).

    Uses the same covariance preconditioning + mean operator as IFSA (via
    _ifsa_target_mean_cov), then measures an affine-invariant distance between
    the two half means.
    """

    n = int(covs.shape[0])
    if n < 4:
        return float("inf")
    mid = n // 2
    covs1 = covs[:mid]
    covs2 = covs[mid:]
    if covs1.shape[0] == 0 or covs2.shape[0] == 0:
        return float("inf")

    # x is unused when covs is provided.
    dummy_x = np.empty((0, 0, 0), dtype=float)
    m1 = _ifsa_target_mean_cov(dummy_x, cov_cfg, cfg, covs=covs1)
    m2 = _ifsa_target_mean_cov(dummy_x, cov_cfg, cfg, covs=covs2)

    d = invsqrtm_spd(sym(m1), eps=cov_cfg.epsilon)
    delta = logm_spd(sym(d @ m2 @ d), eps=cov_cfg.epsilon)
    return float(np.linalg.norm(delta, ord="fro"))


def _ifsa_low_score_hold_decision(
    *,
    score_target: float,
    tau_eff: float,
    safety_low_score_mult: float,
) -> tuple[int, float]:
    """Low-score safety hold decision for target-guided IFSA.

    When the target safety score is *very small* relative to the source-derived
    threshold (tau_eff), we treat alignment as unnecessary and fall back to
    identity to avoid injecting noise.

    Returns:
      (low_hold, low_tau_eff), where low_hold is 1 if the rule triggers, and
      low_tau_eff is safety_low_score_mult * tau_eff (or NaN if disabled).
    """

    safety_low_score_mult = max(0.0, min(1.0, float(safety_low_score_mult)))
    if safety_low_score_mult <= 0.0:
        return 0, float("nan")
    if not (np.isfinite(score_target) and np.isfinite(tau_eff)):
        return 0, float("nan")
    low_tau_eff = float(safety_low_score_mult) * float(tau_eff)
    return (1 if float(score_target) < float(low_tau_eff) else 0), float(low_tau_eff)


def _ifsa_disc_separation_score_from_covs(
    covs: np.ndarray,
    y: np.ndarray,
    *,
    mean_mode: str,
    eps: float,
) -> float:
    """Class separation score in log-Euclidean space (source-only, label-aware).

    For each class, compute its mean covariance (arith or log-euclid), take the
    matrix log, then return the mean pairwise Frobenius distance between class
    log-means.
    """

    if covs.shape[0] != y.shape[0]:
        raise ValueError("covs and y must have the same number of trials")

    logs: list[np.ndarray] = []
    for k in np.unique(y):
        covs_k = covs[y == k]
        if covs_k.shape[0] == 0:
            continue
        if mean_mode == "arith":
            m_k = sym(np.mean(covs_k, axis=0))
        elif mean_mode == "logeuclid":
            m_k = log_euclidean_mean(covs_k, eps=eps)
        else:
            raise ValueError(f"Unknown IFSA mean_mode={mean_mode!r}")
        logs.append(logm_spd(sym(m_k), eps=eps))

    if len(logs) < 2:
        return 0.0

    dists = []
    for i in range(len(logs)):
        for j in range(i + 1, len(logs)):
            dists.append(float(np.linalg.norm(logs[i] - logs[j], ord="fro")))

    if not dists:
        return 0.0

    return float(np.mean(np.asarray(dists, dtype=float)))


def _ifsa_target_dispersion(
    x: np.ndarray,
    cov_cfg: CovarianceConfig,
    cfg: IFSAConfig,
    *,
    reference_cov: np.ndarray,
    target_mean_cov: np.ndarray,
) -> float:
    """Compute target dispersion around desired (unlabeled) in reference coords."""
    covs = compute_covariances(x, cov_cfg)
    if covs.shape[0] == 0:
        raise ValueError("Target alignment subset is empty")

    if cfg.cov_trace_norm:
        dim = covs.shape[1]
        covs = np.stack(
            [
                sym(cov / max(float(cov_cfg.epsilon), float(np.trace(cov)) / float(dim)))
                for cov in covs
            ],
            axis=0,
        )

    alpha = max(0.0, min(0.3, float(cfg.cov_shrink_alpha)))
    if alpha > 0.0:
        dim = covs.shape[1]
        eye = np.eye(dim, dtype=float)
        covs = np.stack(
            [sym((1.0 - alpha) * cov + alpha * (float(np.trace(cov)) / dim) * eye) for cov in covs],
            axis=0,
        )

    strength = max(0.0, min(1.0, float(cfg.cov_log_spec_shrink)))
    if strength > 0.0:
        out = np.empty_like(covs)
        for i, cov in enumerate(covs):
            decomp = eigh_sym(cov)
            values = clamp_eigenvalues(decomp.values, 1e-30)
            log_vals = np.log(values)
            mean_log = float(np.mean(log_vals))
            log_new = mean_log + (1.0 - strength) * (log_vals - mean_log)
            out[i] = sym(decomp.vectors @ np.diag(np.exp(log_new)) @ decomp.vectors.T)
        covs = out

    rho = max(0.0, min(0.99, float(cfg.lr) * float(cfg.lambda_damp)))
    if cfg.damp_mode == "euclid_ema":
        if covs.shape[0] > 1 and rho > 0.0:
            out = np.empty_like(covs)
            out[0] = covs[0]
            for i in range(1, covs.shape[0]):
                out[i] = sym((1.0 - rho) * out[i - 1] + rho * covs[i])
            covs = out
    elif cfg.damp_mode == "log_ema":
        if covs.shape[0] > 1 and rho > 0.0:
            out = np.empty_like(covs)
            prev = logm_spd(covs[0], eps=cov_cfg.epsilon)
            out[0] = covs[0]
            for i in range(1, covs.shape[0]):
                cur = logm_spd(covs[i], eps=cov_cfg.epsilon)
                prev = sym((1.0 - rho) * prev + rho * cur)
                out[i] = expm_sym(prev)
            covs = out
    else:
        raise ValueError(f"Unknown IFSA damp_mode={cfg.damp_mode!r}")

    beta = float(cfg.target_beta)
    desired = sym(reference_cov)
    if beta > 0.0:
        desired = expm_sym(
            (1.0 - beta) * logm_spd(sym(reference_cov), eps=cov_cfg.epsilon)
            + beta * logm_spd(sym(target_mean_cov), eps=cov_cfg.epsilon)
        )

    w_ref = invsqrtm_spd(sym(reference_cov), eps=cov_cfg.epsilon)
    desired_white = sym(w_ref @ desired @ w_ref)
    desired_inv_sqrt = invsqrtm_spd(desired_white, eps=cov_cfg.epsilon)

    cov_w = np.einsum("ij,njk,lk->nil", w_ref, covs, w_ref)
    cov_n = np.einsum("ij,njk,lk->nil", desired_inv_sqrt, cov_w, desired_inv_sqrt)
    vals = []
    for cov in cov_n:
        logm = logm_spd(sym(cov), eps=cov_cfg.epsilon)
        vals.append(float(np.linalg.norm(logm, ord="fro") ** 2))
    if not vals:
        return 0.0
    return float(np.mean(np.asarray(vals, dtype=float)))


def _fit_ifsa_aligners_per_subject(
    x: np.ndarray,
    meta: pd.DataFrame,
    cov_cfg: CovarianceConfig,
    method_cfg: dict,
    reference_cov: np.ndarray,
    *,
    target_mean_cov: np.ndarray | None = None,
    target_dispersion: float | None = None,
    n_jobs: int = 1,
    inplace: bool = False,
) -> tuple[np.ndarray, dict[int, object]]:
    subjects = meta["subject"].to_numpy()
    unique_subjects = np.unique(subjects)
    out = x if inplace else np.empty_like(x)

    cfg = _ifsa_cfg(method_cfg)
    max_jobs = min(int(n_jobs), int(unique_subjects.shape[0])) if int(n_jobs) > 0 else 1

    def _fit_one(s: int) -> tuple[int, object]:
        mask = subjects == s
        x_s = x[mask]
        aligner = IFSASignalAligner(
            cov_cfg,
            cfg,
            reference_cov=reference_cov,
            target_mean_cov=target_mean_cov,
            target_dispersion=target_dispersion,
        ).fit(x_s)
        out[mask] = aligner.transform(x_s)
        return int(s), aligner

    if max_jobs <= 1:
        results = [_fit_one(int(s)) for s in unique_subjects]
    else:
        results = Parallel(n_jobs=max_jobs, prefer="threads")(
            delayed(_fit_one)(int(s)) for s in unique_subjects
        )

    aligners: dict[int, object] = {sid: aligner for sid, aligner in results}

    return out, aligners


def _fit_ifsa_matrices_per_subject(
    x: np.ndarray,
    meta: pd.DataFrame,
    cov_cfg: CovarianceConfig,
    method_cfg: dict,
    reference_cov: np.ndarray,
    *,
    target_mean_cov: np.ndarray | None = None,
    target_dispersion: float | None = None,
    n_jobs: int = 1,
) -> dict[int, np.ndarray]:
    """Fit per-subject IFSA aligners and return only their A matrices.

    Used by safety guards (e.g. disc-loss) to avoid materializing aligned signals.
    """

    subjects = meta["subject"].to_numpy()
    unique_subjects = np.unique(subjects)
    cfg = _ifsa_cfg(method_cfg)
    max_jobs = min(int(n_jobs), int(unique_subjects.shape[0])) if int(n_jobs) > 0 else 1

    def _fit_one(s: int) -> tuple[int, np.ndarray]:
        mask = subjects == s
        x_s = x[mask]
        aligner = IFSASignalAligner(
            cov_cfg,
            cfg,
            reference_cov=reference_cov,
            target_mean_cov=target_mean_cov,
            target_dispersion=target_dispersion,
        ).fit(x_s)
        a = getattr(aligner, "matrix", None)
        if a is None:
            raise RuntimeError("IFSA aligner matrix is None after fit()")
        return int(s), np.asarray(a, dtype=float)

    if max_jobs <= 1:
        results = [_fit_one(int(s)) for s in unique_subjects]
    else:
        results = Parallel(n_jobs=max_jobs, prefer="threads")(
            delayed(_fit_one)(int(s)) for s in unique_subjects
        )

    return {sid: a for sid, a in results}


def _fit_ifsa_target_aligner(
    x_target: np.ndarray,
    cov_cfg: CovarianceConfig,
    method_cfg: dict,
    protocol: ProtocolConfig,
    reference_cov: np.ndarray,
) -> tuple[np.ndarray, object, int]:
    x_for_fit = _target_alignment_subset(x_target, protocol)
    n_fit = int(x_for_fit.shape[0])

    cfg = _ifsa_cfg(method_cfg)
    aligner = IFSASignalAligner(cov_cfg, cfg, reference_cov=reference_cov).fit(x_for_fit)
    return aligner.transform(x_target), aligner, n_fit


def _fit_signal_aligners_per_subject(
    x: np.ndarray,
    meta: pd.DataFrame,
    cov_cfg: CovarianceConfig,
    method_name: str,
    method_cfg: dict,
    *,
    n_jobs: int = 1,
    inplace: bool = False,
) -> tuple[np.ndarray, dict[int, object]]:
    subjects = meta["subject"].to_numpy()
    unique_subjects = np.unique(subjects)
    out = x if inplace else np.empty_like(x)
    max_jobs = min(int(n_jobs), int(unique_subjects.shape[0])) if int(n_jobs) > 0 else 1

    def _fit_one(s: int) -> tuple[int, object]:
        mask = subjects == s
        x_s = x[mask]

        if method_name == "identity":
            aligner = IdentitySignalAligner(n_channels=x.shape[1])
        elif method_name == "ea":
            aligner = EASignalAligner(cov_cfg).fit(x_s)
        elif method_name == "ra":
            aligner = RASignalAligner(cov_cfg).fit(x_s)
        elif method_name == "ra_riemann":
            from eapp.alignment.ra_riemann import RARiemannSignalAligner

            aligner = RARiemannSignalAligner(cov_cfg).fit(x_s)
        else:
            raise ValueError(f"Unsupported signal method: {method_name}")

        out[mask] = aligner.transform(x_s)
        return int(s), aligner

    if max_jobs <= 1:
        results = [_fit_one(int(s)) for s in unique_subjects]
    else:
        results = Parallel(n_jobs=max_jobs, prefer="threads")(
            delayed(_fit_one)(int(s)) for s in unique_subjects
        )

    aligners: dict[int, object] = {sid: aligner for sid, aligner in results}
    return out, aligners


def _fit_target_aligner(
    x_target: np.ndarray,
    cov_cfg: CovarianceConfig,
    method_name: str,
    method_cfg: dict,
    protocol: ProtocolConfig,
) -> tuple[np.ndarray, object, int]:
    x_for_fit = _target_alignment_subset(x_target, protocol)
    n_fit = int(x_for_fit.shape[0])

    if method_name == "identity":
        aligner = IdentitySignalAligner(n_channels=x_target.shape[1])
    elif method_name == "ea":
        aligner = EASignalAligner(cov_cfg).fit(x_for_fit)
    elif method_name == "ra":
        aligner = RASignalAligner(cov_cfg).fit(x_for_fit)
    elif method_name == "ra_riemann":
        from eapp.alignment.ra_riemann import RARiemannSignalAligner

        aligner = RARiemannSignalAligner(cov_cfg).fit(x_for_fit)
    else:
        raise ValueError(f"Unsupported signal method: {method_name}")

    return aligner.transform(x_target), aligner, n_fit


def _run_signal_fold(
    *,
    x: np.ndarray,
    y: np.ndarray,
    meta: pd.DataFrame,
    train_idx: np.ndarray,
    test_idx: np.ndarray,
    protocol: ProtocolConfig,
    cov_cfg: CovarianceConfig,
    method_name: str,
    method_cfg: dict,
    model_name: str,
    model_cfg: dict,
    subject_n_jobs: int = 1,
) -> tuple[float, float, int, dict]:
    x_train = x[train_idx]
    y_train = y[train_idx]
    meta_train = meta.iloc[train_idx]
    x_test = x[test_idx]
    y_test = y[test_idx]

    extra_gate: dict[str, float | int] = {}

    if method_name == "coral":
        mean_mode = str(method_cfg.get("mean_mode", "logeuclid"))
        x_fit = _target_alignment_subset(x_test, protocol)
        n_fit = int(x_fit.shape[0])
        if n_fit == 0:
            raise RuntimeError("CORAL requires non-empty target alignment subset")

        covs_t = compute_covariances(x_fit, cov_cfg)
        if mean_mode == "arith":
            target_mean_cov = sym(np.mean(covs_t, axis=0))
        elif mean_mode == "logeuclid":
            target_mean_cov = log_euclidean_mean(covs_t, eps=cov_cfg.epsilon)
        else:
            raise ValueError(f"Unknown CORAL mean_mode={mean_mode!r}")

        subjects = meta_train["subject"].to_numpy()
        x_train_aligned = x_train
        for s in np.unique(subjects):
            mask = subjects == s
            x_s = x_train[mask]
            aligner = CoralSignalAligner(
                cov_cfg,
                target_mean_cov=target_mean_cov,
                mean_mode=mean_mode,
            ).fit(x_s)
            x_train_aligned[mask] = aligner.transform(x_s)

        x_test_aligned = x_test
        target_aligner = IdentitySignalAligner(n_channels=x.shape[1])

    elif method_name == "coral_safe":
        mean_mode = str(method_cfg.get("mean_mode", "logeuclid"))
        safety_quantile = float(method_cfg.get("safety_quantile", 0.90))
        safety_tau_mult = float(method_cfg.get("safety_tau_mult", 1.0))
        safety_disc_loss_tau = float(method_cfg.get("safety_disc_loss_tau", 0.001))

        safety_quantile = max(0.0, min(1.0, safety_quantile))
        safety_tau_mult = max(0.0, safety_tau_mult)
        safety_disc_loss_tau = max(0.0, min(1.0, safety_disc_loss_tau))

        x_fit = _target_alignment_subset(x_test, protocol)
        n_fit = int(x_fit.shape[0])
        if n_fit == 0:
            raise RuntimeError("coral_safe requires non-empty target alignment subset")

        covs_fit = compute_covariances(x_fit, cov_cfg)
        if mean_mode == "arith":
            target_mean_cov = sym(np.mean(covs_fit, axis=0))
        elif mean_mode == "logeuclid":
            target_mean_cov = log_euclidean_mean(covs_fit, eps=cov_cfg.epsilon)
        else:
            raise ValueError(f"Unknown coral_safe mean_mode={mean_mode!r}")

        subjects = meta_train["subject"].to_numpy()
        covs_train = compute_covariances(x_train, cov_cfg)

        def _mean_cov(covs: np.ndarray) -> np.ndarray:
            if mean_mode == "arith":
                return sym(np.mean(covs, axis=0))
            if mean_mode == "logeuclid":
                return log_euclidean_mean(covs, eps=cov_cfg.epsilon)
            raise ValueError(f"Unknown coral_safe mean_mode={mean_mode!r}")

        # Source-only reference covariance (for OOD scoring): log-Euclidean mean
        # over source-subject means.
        means = []
        for s in np.unique(subjects):
            covs_s = covs_train[subjects == s]
            if covs_s.shape[0] == 0:
                continue
            means.append(_mean_cov(covs_s))
        if not means:
            raise RuntimeError("coral_safe failed to compute source reference covariance")
        reference_cov = log_euclidean_mean(np.stack(means, axis=0), eps=cov_cfg.epsilon)
        w_ref = invsqrtm_spd(reference_cov, eps=cov_cfg.epsilon)

        def _score_track_error(covs: np.ndarray) -> float:
            cov_w = np.einsum("ij,njk,lk->nil", w_ref, covs, w_ref)
            mean_white = _mean_cov(cov_w)
            err0 = logm_spd(mean_white, eps=cov_cfg.epsilon)
            return float(np.linalg.norm(err0, ord="fro"))

        score_target = _score_track_error(covs_fit)
        errors_source = []
        for s in np.unique(subjects):
            covs_s = covs_train[subjects == s]
            if covs_s.shape[0] == 0:
                continue
            errors_source.append(_score_track_error(covs_s))
        if not errors_source:
            raise RuntimeError("coral_safe failed to compute safety threshold (no source errors)")
        tau_source = float(np.quantile(np.asarray(errors_source, dtype=float), safety_quantile))
        tau_eff = float(safety_tau_mult) * float(tau_source)

        # Candidate CORAL alignment on source subjects (always safe for target;
        # we keep target identity).
        x_train_candidate = np.empty_like(x_train)
        covs_candidate = np.empty_like(covs_train)
        for s in np.unique(subjects):
            mask = subjects == s
            x_s = x_train[mask]
            covs_s = covs_train[mask]
            if x_s.shape[0] == 0:
                continue
            source_mean_cov = _mean_cov(covs_s)
            a = coral_matrix(
                source_mean_cov=source_mean_cov,
                target_mean_cov=target_mean_cov,
                eps=cov_cfg.epsilon,
            )
            x_train_candidate[mask] = np.einsum("ij,njt->nit", a, x_s)
            covs_candidate[mask] = np.stack([a @ cov @ a.T for cov in covs_s], axis=0)

        hold = 0
        gate_factor = 1.0
        disc_loss_val = float("nan")
        disc_loss_tau_eff = float(safety_disc_loss_tau)

        if (
            np.isfinite(score_target)
            and np.isfinite(tau_eff)
            and float(score_target) > float(tau_eff)
        ):
            # Secondary guard: only hold if CORAL actually collapses
            # source discriminative structure.
            disc_before = _ifsa_disc_separation_score_from_covs(
                covs_train,
                y_train,
                mean_mode=mean_mode,
                eps=cov_cfg.epsilon,
            )
            disc_after = _ifsa_disc_separation_score_from_covs(
                covs_candidate,
                y_train,
                mean_mode=mean_mode,
                eps=cov_cfg.epsilon,
            )
            disc_loss_val = max(
                0.0,
                1.0 - float(disc_after) / max(1e-12, float(disc_before)),
            )

            if safety_disc_loss_tau <= 0.0 or (
                np.isfinite(disc_loss_val) and disc_loss_val > float(safety_disc_loss_tau)
            ):
                hold = 1
                gate_factor = 0.0

        if hold == 1:
            x_train_aligned = x_train
        else:
            x_train_aligned = x_train_candidate

        x_test_aligned = x_test
        target_aligner = IdentitySignalAligner(n_channels=x.shape[1])

        # Reuse the existing safety columns for analysis/debugging.
        extra_gate = {
            "ifsa_safety_gate_factor": float(gate_factor),
            "ifsa_safety_hold": int(hold),
            "ifsa_safety_score_mode": 0,  # track_error
            "ifsa_safety_score_target": float(score_target),
            "ifsa_safety_tau_source": float(tau_source),
            "ifsa_safety_tau_eff": float(tau_eff),
            "ifsa_safety_quantile": float(safety_quantile),
            "ifsa_safety_disc_loss": float(disc_loss_val),
            "ifsa_safety_disc_loss_tau": float(disc_loss_tau_eff),
        }

    elif method_name == "tl_center_scale":
        if model_name != "mdm":
            raise ValueError("tl_center_scale is only supported with model=mdm")

        from pyriemann.transfer import TLCenter, TLScale, encode_domains

        x_fit = _target_alignment_subset(x_test, protocol)
        n_fit = int(x_fit.shape[0])
        if n_fit == 0:
            raise RuntimeError("tl_center_scale requires non-empty target alignment subset")

        covs_train = compute_covariances(x_train, cov_cfg)
        covs_test = compute_covariances(x_test, cov_cfg)
        covs_target_fit = compute_covariances(x_fit, cov_cfg)

        meta_test = meta.iloc[test_idx].iloc[:n_fit]
        domains_train = meta_train["subject"].to_numpy()
        domains_target = meta_test["subject"].to_numpy()

        # TLCenter/TLScale only require domains; keep labels as placeholders.
        y_dummy_target = np.zeros(n_fit, dtype=int)
        covs_all = np.concatenate([covs_train, covs_target_fit], axis=0)
        y_all = np.concatenate([y_train, y_dummy_target], axis=0)
        domains_all = np.concatenate([domains_train, domains_target], axis=0)

        _, y_enc = encode_domains(covs_all, y_all, domains_all)
        target_domain = str(int(domains_target[0]))

        center = TLCenter(target_domain=target_domain, metric="riemann")
        covs_centered = center.fit_transform(covs_all, y_enc)

        scale = TLScale(
            target_domain=target_domain,
            final_dispersion=1.0,
            centered_data=True,
            metric="riemann",
        )
        covs_scaled = scale.fit_transform(covs_centered, y_enc)
        covs_train_scaled = covs_scaled[: covs_train.shape[0]]

        covs_test_centered = center.transform(covs_test)
        covs_test_scaled = scale.transform(covs_test_centered)

        from eapp.models.mdm import MDMClassifier, MDMConfig

        clf = MDMClassifier(MDMConfig(metric=str(model_cfg["metric"])))
        clf.fit(covs_train_scaled, y_train)
        y_pred = clf.predict(covs_test_scaled)

        metrics = compute_metrics(y_test, y_pred)
        return metrics.acc, metrics.kappa, n_fit, {}

    elif method_name == "ifsa":
        cfg_ifsa = _ifsa_cfg(method_cfg)
        ref = _ifsa_reference_cov(x_train, meta_train, cov_cfg, method_cfg)

        method_cfg_eff = method_cfg
        covs_train = None
        if cfg_ifsa.trigger_mode == "source_quantile":
            subjects = meta_train["subject"].to_numpy()
            covs_train = compute_covariances(x_train, cov_cfg)
            errors = []
            for s in np.unique(subjects):
                covs_s = covs_train[subjects == s]
                if covs_s.shape[0] == 0:
                    continue
                errors.append(
                    _ifsa_track_error_before_from_covs(
                        covs_s,
                        cfg_ifsa,
                        reference_cov=ref,
                        eps=cov_cfg.epsilon,
                    )
                )
            if not errors:
                raise RuntimeError("Failed to compute IFSA source-quantile trigger threshold")
            tau_eff = float(
                np.quantile(
                    np.asarray(errors, dtype=float),
                    float(cfg_ifsa.trigger_quantile),
                )
            )
            method_cfg_eff = dict(method_cfg)
            method_cfg_eff["trigger_tau"] = tau_eff

        if float(cfg_ifsa.target_beta) > 0.0:
            x_fit = _target_alignment_subset(x_test, protocol)
            n_fit = int(x_fit.shape[0])
            if n_fit == 0:
                raise RuntimeError(
                    "IFSA target-guided mode requires non-empty target alignment subset"
                )

            covs_fit = compute_covariances(x_fit, cov_cfg)

            safety_score_mode = str(method_cfg_eff.get("safety_score_mode", "track_error"))
            safety_mode = str(method_cfg_eff.get("safety_mode", "none"))
            safety_quantile = float(method_cfg_eff.get("safety_quantile", 0.95))
            safety_tau_mult = float(method_cfg_eff.get("safety_tau_mult", 1.0))
            safety_gain_min = float(method_cfg_eff.get("safety_gain_min", 0.0))
            safety_hold_gate_threshold = float(
                method_cfg_eff.get("safety_hold_gate_threshold", 0.0)
            )
            safety_disc_loss_tau = float(method_cfg_eff.get("safety_disc_loss_tau", 0.0))
            safety_low_score_mult = float(method_cfg_eff.get("safety_low_score_mult", 0.0))
            safety_disc_scale_tau = float(method_cfg_eff.get("safety_disc_scale_tau", 0.0))
            safety_disc_scale_max_trials_per_class = int(
                method_cfg_eff.get("safety_disc_scale_max_trials_per_class", 0)
            )

            safety_quantile = max(0.0, min(1.0, safety_quantile))
            safety_tau_mult = max(0.0, safety_tau_mult)
            safety_gain_min = max(0.0, min(1.0, safety_gain_min))
            safety_hold_gate_threshold = max(0.0, min(1.0, safety_hold_gate_threshold))
            safety_disc_loss_tau = max(0.0, min(1.0, safety_disc_loss_tau))
            safety_low_score_mult = max(0.0, min(1.0, safety_low_score_mult))
            safety_disc_scale_tau = max(0.0, min(1.0, safety_disc_scale_tau))
            safety_disc_scale_max_trials_per_class = max(
                0, int(safety_disc_scale_max_trials_per_class)
            )

            gate_factor = 1.0
            tau_source = float("nan")
            tau_eff = float("nan")
            hold = 0
            disc_loss_val = float("nan")
            disc_loss_tau_eff = float(safety_disc_loss_tau)
            low_tau_eff = float("nan")
            low_hold = 0
            disc_scale_factor = 1.0
            disc_scale_triggered = 0

            if safety_score_mode == "disc_loss":
                score_mode_id = 2

                if covs_train is None:
                    covs_train = compute_covariances(x_train, cov_cfg)
                disc_before = _ifsa_disc_separation_score_from_covs(
                    covs_train,
                    y_train,
                    mean_mode=str(cfg_ifsa.mean_mode),
                    eps=cov_cfg.epsilon,
                )

                target_mean_cov = _ifsa_target_mean_cov(
                    x_fit,
                    cov_cfg,
                    cfg_ifsa,
                    covs=covs_fit,
                )
                target_disp = None
                if float(cfg_ifsa.lambda_disp) > 0.0:
                    target_disp = _ifsa_target_dispersion(
                        x_fit,
                        cov_cfg,
                        cfg_ifsa,
                        reference_cov=ref,
                        target_mean_cov=target_mean_cov,
                    )

                # Candidate source->target alignment (used both for scoring and, if safe,
                # for training). Target data remains identity in target-guided mode.
                a_by_subject = _fit_ifsa_matrices_per_subject(
                    x_train,
                    meta_train,
                    cov_cfg,
                    method_cfg_eff,
                    ref,
                    target_mean_cov=target_mean_cov,
                    target_dispersion=target_disp,
                    n_jobs=int(subject_n_jobs),
                )
                subjects = meta_train["subject"].to_numpy()
                covs_candidate = np.empty_like(covs_train)
                for s in np.unique(subjects):
                    mask = subjects == s
                    a = a_by_subject[int(s)]
                    covs_candidate[mask] = np.einsum(
                        "ij,njk,lk->nil",
                        a,
                        covs_train[mask],
                        a,
                    )
                disc_after = _ifsa_disc_separation_score_from_covs(
                    covs_candidate,
                    y_train,
                    mean_mode=str(cfg_ifsa.mean_mode),
                    eps=cov_cfg.epsilon,
                )
                score_target = max(
                    0.0,
                    1.0 - float(disc_after) / max(1e-12, float(disc_before)),
                )
                disc_loss_val = float(score_target)

                tau_eff = float(safety_tau_mult)
                disc_loss_tau_eff = float(tau_eff)
                if safety_mode == "none":
                    gate_factor = 1.0
                    hold = 0
                elif safety_mode == "hold_identity":
                    if np.isfinite(score_target) and np.isfinite(tau_eff) and float(
                        score_target
                    ) > float(tau_eff):
                        gate_factor = 0.0
                        hold = 1
                    else:
                        gate_factor = 1.0
                        hold = 0
                elif safety_mode == "scale_gain":
                    raise ValueError(
                        "IFSA safety_mode=scale_gain is not supported with safety_score_mode="
                        "disc_loss (v20); use hold_identity"
                    )
                else:
                    raise ValueError(f"Unknown IFSA safety_mode={safety_mode!r}")

                if gate_factor <= 0.0:
                    x_train_aligned = x_train
                    x_test_aligned = x_test
                    target_aligner = IdentitySignalAligner(n_channels=x.shape[1])
                else:
                    x_train_aligned, _ = _fit_ifsa_aligners_per_subject(
                        x_train,
                        meta_train,
                        cov_cfg,
                        method_cfg_eff,
                        ref,
                        target_mean_cov=target_mean_cov,
                        target_dispersion=target_disp,
                        n_jobs=int(subject_n_jobs),
                        inplace=True,
                    )
                    x_test_aligned = x_test
                    target_aligner = IdentitySignalAligner(n_channels=x.shape[1])
            else:
                if safety_score_mode == "track_error":
                    score_mode_id = 0
                    score_target = _ifsa_track_error_before_from_covs(
                        covs_fit,
                        cfg_ifsa,
                        reference_cov=ref,
                        eps=cov_cfg.epsilon,
                    )
                elif safety_score_mode == "split_half":
                    score_mode_id = 1
                    score_target = _ifsa_split_half_stability_score_from_covs(
                        covs_fit,
                        cov_cfg,
                        cfg_ifsa,
                    )
                else:
                    raise ValueError(f"Unknown IFSA safety_score_mode={safety_score_mode!r}")

                if safety_mode != "none":
                    subjects = meta_train["subject"].to_numpy()
                    if covs_train is None:
                        covs_train = compute_covariances(x_train, cov_cfg)

                    errors_source = []
                    for s in np.unique(subjects):
                        covs_s = covs_train[subjects == s]
                        if covs_s.shape[0] == 0:
                            continue
                        if safety_score_mode == "track_error":
                            errors_source.append(
                                _ifsa_track_error_before_from_covs(
                                    covs_s,
                                    cfg_ifsa,
                                    reference_cov=ref,
                                    eps=cov_cfg.epsilon,
                                )
                            )
                        elif safety_score_mode == "split_half":
                            errors_source.append(
                                _ifsa_split_half_stability_score_from_covs(
                                    covs_s,
                                    cov_cfg,
                                    cfg_ifsa,
                                )
                            )
                        else:
                            raise ValueError(
                                f"Unknown IFSA safety_score_mode={safety_score_mode!r}"
                            )
                    if not errors_source:
                        raise RuntimeError(
                            "Failed to compute IFSA safety threshold (no source errors)"
                        )

                    tau_source = float(
                        np.quantile(
                            np.asarray(errors_source, dtype=float),
                            safety_quantile,
                        )
                    )
                    tau_eff = float(safety_tau_mult) * float(tau_source)

                    if safety_mode == "scale_gain":
                        if (
                            score_target > 0.0
                            and np.isfinite(score_target)
                            and np.isfinite(tau_eff)
                        ):
                            gate_factor = float(tau_eff / max(1e-12, float(score_target)))
                        else:
                            gate_factor = 1.0
                        gate_factor = max(safety_gain_min, min(1.0, gate_factor))
                        if (
                            safety_hold_gate_threshold > 0.0
                            and np.isfinite(gate_factor)
                            and float(gate_factor) < float(safety_hold_gate_threshold)
                        ):
                            gate_factor = 0.0
                            hold = 1
                    elif safety_mode == "hold_identity":
                        if (
                            np.isfinite(score_target)
                            and np.isfinite(tau_eff)
                            and float(score_target) > float(tau_eff)
                        ):
                            gate_factor = 0.0
                            hold = 1
                        else:
                            gate_factor = 1.0
                            hold = 0
                    else:
                        raise ValueError(f"Unknown IFSA safety_mode={safety_mode!r}")

                if (
                    safety_disc_loss_tau > 0.0
                    and safety_score_mode == "track_error"
                    and (
                        (safety_mode == "hold_identity" and hold == 1)
                        or (safety_mode == "scale_gain" and float(gate_factor) < 1.0)
                    )
                ):
                    if covs_train is None:
                        covs_train = compute_covariances(x_train, cov_cfg)
                    disc_before = _ifsa_disc_separation_score_from_covs(
                        covs_train,
                        y_train,
                        mean_mode=str(cfg_ifsa.mean_mode),
                        eps=cov_cfg.epsilon,
                    )

                    target_mean_cov = _ifsa_target_mean_cov(
                        x_fit,
                        cov_cfg,
                        cfg_ifsa,
                        covs=covs_fit,
                    )
                    target_disp = None
                    if float(cfg_ifsa.lambda_disp) > 0.0:
                        target_disp = _ifsa_target_dispersion(
                            x_fit,
                            cov_cfg,
                            cfg_ifsa,
                            reference_cov=ref,
                            target_mean_cov=target_mean_cov,
                        )

                    a_by_subject = _fit_ifsa_matrices_per_subject(
                        x_train,
                        meta_train,
                        cov_cfg,
                        method_cfg_eff,
                        ref,
                        target_mean_cov=target_mean_cov,
                        target_dispersion=target_disp,
                        n_jobs=int(subject_n_jobs),
                    )
                    subjects = meta_train["subject"].to_numpy()
                    covs_candidate = np.empty_like(covs_train)
                    for s in np.unique(subjects):
                        mask = subjects == s
                        a = a_by_subject[int(s)]
                        covs_candidate[mask] = np.einsum(
                            "ij,njk,lk->nil",
                            a,
                            covs_train[mask],
                            a,
                        )
                    disc_after = _ifsa_disc_separation_score_from_covs(
                        covs_candidate,
                        y_train,
                        mean_mode=str(cfg_ifsa.mean_mode),
                        eps=cov_cfg.epsilon,
                    )
                    disc_loss_val = max(
                        0.0,
                        1.0 - float(disc_after) / max(1e-12, float(disc_before)),
                    )

                    if np.isfinite(disc_loss_val) and disc_loss_val <= float(safety_disc_loss_tau):
                        gate_factor = 1.0
                        hold = 0

                # Optional v30 low-score hold (only when safety is enabled).
                if safety_mode != "none" and safety_low_score_mult > 0.0:
                    low_hold, low_tau_eff = _ifsa_low_score_hold_decision(
                        score_target=float(score_target),
                        tau_eff=float(tau_eff),
                        safety_low_score_mult=float(safety_low_score_mult),
                    )
                    if low_hold == 1:
                        gate_factor = 0.0
                        hold = 1

                if gate_factor <= 0.0:
                    x_train_aligned = x_train
                    x_test_aligned = x_test
                    target_aligner = IdentitySignalAligner(n_channels=x.shape[1])
                else:
                    method_cfg_eff2 = dict(method_cfg_eff)
                    method_cfg_eff2["lambda_track"] = (
                        float(method_cfg_eff2["lambda_track"]) * float(gate_factor)
                    )

                    target_mean_cov = _ifsa_target_mean_cov(
                        x_fit,
                        cov_cfg,
                        cfg_ifsa,
                        covs=covs_fit,
                    )
                    target_disp = None
                    if float(cfg_ifsa.lambda_disp) > 0.0:
                        target_disp = _ifsa_target_dispersion(
                            x_fit,
                            cov_cfg,
                            cfg_ifsa,
                            reference_cov=ref,
                            target_mean_cov=target_mean_cov,
                        )
                    a_by_subject = _fit_ifsa_matrices_per_subject(
                        x_train,
                        meta_train,
                        cov_cfg,
                        method_cfg_eff2,
                        ref,
                        target_mean_cov=target_mean_cov,
                        target_dispersion=target_disp,
                        n_jobs=int(subject_n_jobs),
                    )

                    # Disc-loss thrust attenuation (v3): only apply when the
                    # primary safety gate is already scaling down (gate_factor < 1).
                    # This avoids shrinking otherwise-safe folds to (near) identity.
                    if (
                        safety_mode == "scale_gain"
                        and safety_disc_scale_tau > 0.0
                        and np.isfinite(gate_factor)
                        and float(gate_factor) < 1.0
                    ):
                        if covs_train is None:
                            covs_train = compute_covariances(x_train, cov_cfg)

                        rng = np.random.default_rng(0)
                        max_trials_per_class = int(safety_disc_scale_max_trials_per_class)
                        sample_idx_parts = []
                        for k in np.unique(y_train):
                            idx_k = np.flatnonzero(y_train == k)
                            if (
                                max_trials_per_class > 0
                                and idx_k.shape[0] > max_trials_per_class
                            ):
                                idx_k = rng.choice(
                                    idx_k,
                                    size=max_trials_per_class,
                                    replace=False,
                                )
                            sample_idx_parts.append(np.asarray(idx_k, dtype=int))
                        sample_idx = (
                            np.sort(np.unique(np.concatenate(sample_idx_parts)))
                            if sample_idx_parts
                            else np.asarray([], dtype=int)
                        )

                        if sample_idx.shape[0] > 0:
                            covs_sample = covs_train[sample_idx]
                            y_sample = y_train[sample_idx]
                            subjects_sample = meta_train["subject"].to_numpy()[sample_idx]

                            disc_before = _ifsa_disc_separation_score_from_covs(
                                covs_sample,
                                y_sample,
                                mean_mode=str(cfg_ifsa.mean_mode),
                                eps=cov_cfg.epsilon,
                            )
                            if disc_before > 0.0 and np.isfinite(disc_before):
                                covs_sample_aligned = np.empty_like(covs_sample)
                                for s in np.unique(subjects_sample):
                                    mask = subjects_sample == s
                                    a = a_by_subject[int(s)]
                                    covs_sample_aligned[mask] = np.einsum(
                                        "ij,njk,lk->nil",
                                        a,
                                        covs_sample[mask],
                                        a,
                                    )
                                disc_after = _ifsa_disc_separation_score_from_covs(
                                    covs_sample_aligned,
                                    y_sample,
                                    mean_mode=str(cfg_ifsa.mean_mode),
                                    eps=cov_cfg.epsilon,
                                )
                                disc_loss_scale = max(
                                    0.0,
                                    1.0 - float(disc_after) / max(1e-12, float(disc_before)),
                                )

                                if not np.isfinite(disc_loss_val):
                                    disc_loss_val = float(disc_loss_scale)

                                if (
                                    np.isfinite(disc_loss_scale)
                                    and float(disc_loss_scale) > float(safety_disc_scale_tau)
                                ):
                                    disc_scale_factor = float(safety_disc_scale_tau) / max(
                                        1e-12, float(disc_loss_scale)
                                    )
                                    disc_scale_factor = max(0.0, min(1.0, disc_scale_factor))
                                    disc_scale_triggered = 1

                                del covs_sample_aligned
                            del covs_sample

                    x_train_aligned = x_train
                    subjects = meta_train["subject"].to_numpy()
                    unique_subjects = np.unique(subjects)
                    identity = np.eye(x.shape[1], dtype=float)
                    thrust_mode = str(getattr(cfg_ifsa, "thrust_mode", "spd"))
                    for s in unique_subjects:
                        mask = subjects == s
                        x_s = x_train[mask]
                        a = a_by_subject[int(s)]
                        a_eff = a
                        if disc_scale_factor < 1.0:
                            if thrust_mode == "spd":
                                a_eff = expm_sym(
                                    float(disc_scale_factor)
                                    * logm_spd(sym(a), eps=cov_cfg.epsilon)
                                )
                            else:
                                a_eff = (1.0 - float(disc_scale_factor)) * identity + float(
                                    disc_scale_factor
                                ) * a
                        x_train_aligned[mask] = np.einsum("ij,njt->nit", a_eff, x_s)
                    x_test_aligned = x_test
                    target_aligner = IdentitySignalAligner(n_channels=x.shape[1])

            extra_gate = {
                "ifsa_safety_gate_factor": float(gate_factor),
                "ifsa_safety_hold": int(hold),
                "ifsa_safety_score_mode": int(score_mode_id),
                "ifsa_safety_score_target": float(score_target),
                "ifsa_safety_tau_source": float(tau_source),
                "ifsa_safety_tau_eff": float(tau_eff),
                "ifsa_safety_quantile": float(safety_quantile),
                "ifsa_safety_disc_loss": float(disc_loss_val),
                "ifsa_safety_disc_loss_tau": float(disc_loss_tau_eff),
                "ifsa_safety_low_score_mult": float(safety_low_score_mult),
                "ifsa_safety_low_tau_eff": float(low_tau_eff),
                "ifsa_safety_low_hold": int(low_hold),
                "ifsa_safety_disc_scale_tau": float(safety_disc_scale_tau),
                "ifsa_safety_disc_scale_max_trials_per_class": int(
                    safety_disc_scale_max_trials_per_class
                ),
                "ifsa_safety_disc_scale_factor": float(disc_scale_factor),
                "ifsa_safety_disc_scale_triggered": int(disc_scale_triggered),
            }
        else:
            x_train_aligned, _ = _fit_ifsa_aligners_per_subject(
                x_train,
                meta_train,
                cov_cfg,
                method_cfg_eff,
                ref,
                n_jobs=int(subject_n_jobs),
                inplace=True,
            )
            x_test_aligned, target_aligner, n_fit = _fit_ifsa_target_aligner(
                x_test,
                cov_cfg,
                method_cfg_eff,
                protocol,
                ref,
            )
    else:
        x_train_aligned, _ = _fit_signal_aligners_per_subject(
            x_train,
            meta_train,
            cov_cfg,
            method_name,
            method_cfg,
            n_jobs=int(subject_n_jobs),
            inplace=True,
        )
        x_test_aligned, target_aligner, n_fit = _fit_target_aligner(
            x_test, cov_cfg, method_name, method_cfg, protocol
        )

    if model_name == "csp_lda":
        from eapp.models.csp_lda import CSPLDAClassifier, CSPLDAConfig

        clf = CSPLDAClassifier(
            CSPLDAConfig(n_components=int(model_cfg["n_components"]), reg=model_cfg["reg"])
        )
        clf.fit(x_train_aligned, y_train)
        y_pred = clf.predict(x_test_aligned)
    elif model_name == "mdm":
        from eapp.models.mdm import MDMClassifier, MDMConfig

        covs_train = compute_covariances(x_train_aligned, cov_cfg)
        covs_test = compute_covariances(x_test_aligned, cov_cfg)
        clf = MDMClassifier(MDMConfig(metric=str(model_cfg["metric"])))
        clf.fit(covs_train, y_train)
        y_pred = clf.predict(covs_test)
    else:
        raise ValueError(f"Unsupported model for signal pipeline: {model_name}")

    metrics = compute_metrics(y_test, y_pred)
    extra = _metrics_to_extra(getattr(target_aligner, "metrics", None))
    extra.update(extra_gate)
    return metrics.acc, metrics.kappa, n_fit, extra


def _run_tangent_fold(
    *,
    x: np.ndarray,
    y: np.ndarray,
    meta: pd.DataFrame,
    classes: np.ndarray,
    train_idx: np.ndarray,
    test_idx: np.ndarray,
    protocol: ProtocolConfig,
    cov_cfg: CovarianceConfig,
    method_name: str,
    method_cfg: dict,
    model_name: str,
) -> tuple[float, float, int, dict]:
    if model_name != "tangent_lda":
        raise ValueError("Tangent pipeline currently supports model=tangent_lda only")

    x_train = x[train_idx]
    y_train = y[train_idx]
    meta_train = meta.iloc[train_idx]
    x_test = x[test_idx]
    y_test = y[test_idx]

    covs_train = compute_covariances(x_train, cov_cfg)
    covs_test = compute_covariances(x_test, cov_cfg)

    # Target labels are never used for anchors unless in few-shot mode.
    y_target_for_anchors = None
    if protocol.target_data_usage == "few_shot_labeled":
        n = int(min(protocol.few_shot_n_trials, y_test.shape[0]))
        y_target_for_anchors = y_test[:n]

    n_fit = int(_target_alignment_subset(x_test, protocol).shape[0])
    covs_fit = covs_test[:n_fit]

    extra: dict = {}
    if method_name == "tangent_identity":
        from eapp.alignment.tsa import _apply_recenter, _recenter_matrix  # local import (MVP)
        from eapp.representation.tangent import tangent_space_identity

        src_r = _recenter_matrix(covs_train, eps=cov_cfg.epsilon)
        tgt_r = _recenter_matrix(covs_fit, eps=cov_cfg.epsilon)
        covs_train_c = _apply_recenter(covs_train, src_r)
        covs_test_c = _apply_recenter(covs_test, tgt_r)
        z_train = tangent_space_identity(covs_train_c, eps=cov_cfg.epsilon)
        z_test = tangent_space_identity(covs_test_c, eps=cov_cfg.epsilon)
    elif method_name == "tsa":
        res = align_tangent_space(
            source_covs=covs_train,
            source_y=y_train,
            source_classes=np.arange(classes.shape[0]),
            target_covs=covs_test,
            target_covs_fit=covs_fit,
            target_y_for_anchors=y_target_for_anchors,
            cfg=TSAConfig(anchor_strategy=str(method_cfg["anchor_strategy"])),
            eps=cov_cfg.epsilon,
        )
        z_train = res.source_z
        z_test = res.target_z_aligned
    elif method_name == "tsa_ss":
        res = align_tangent_space_with_stable_subspace(
            source_covs=covs_train,
            source_y=y_train,
            source_classes=np.arange(classes.shape[0]),
            source_subjects=meta_train["subject"].to_numpy(),
            target_covs=covs_test,
            target_covs_fit=covs_fit,
            target_y_for_anchors=y_target_for_anchors,
            cfg=TSASSConfig(
                anchor_strategy=str(method_cfg["anchor_strategy"]),
                k_dim=int(method_cfg["k_dim"]),
                subspace_lock_weight=float(method_cfg["subspace_lock_weight"]),
            ),
            eps=cov_cfg.epsilon,
        )
        z_train = res.source_z
        z_test = res.target_z_aligned
        extra = {
            "principal_angle_deg_mean": res.principal_angle_deg_mean,
            "subspace_similarity_mean": res.subspace_similarity_mean,
        }
    else:
        raise ValueError(f"Unsupported tangent method: {method_name}")

    from eapp.models.tangent_lda import TangentLDAClassifier

    clf = TangentLDAClassifier().fit(z_train, y_train)
    y_pred = clf.predict(z_test)
    metrics = compute_metrics(y_test, y_pred)
    return metrics.acc, metrics.kappa, n_fit, extra


def run_loso(
    *,
    x: np.ndarray,
    y: np.ndarray,
    meta: pd.DataFrame,
    classes: np.ndarray,
    protocol_cfg: ProtocolConfig,
    method_name: str,
    method_cfg: dict,
    model_name: str,
    model_cfg: dict,
    cov_cfg: CovarianceConfig,
    compute_baseline: bool,
    baseline_method: str,
    n_jobs: int = 1,
    subject_n_jobs: int = 1,
    trim_memory: bool = False,
) -> pd.DataFrame:
    folds = _split_loso(meta)
    fold_n_jobs = max(1, int(n_jobs))
    subj_n_jobs = max(1, int(subject_n_jobs))
    if fold_n_jobs > 1:
        # Avoid nested parallelism by default.
        subj_n_jobs = 1

    def _run_one_fold(
        target_subject: int, train_idx: np.ndarray, test_idx: np.ndarray
    ) -> tuple[dict, tuple[float, float] | None]:
        start = time.perf_counter()
        if method_name in {
            "identity",
            "ea",
            "ra",
            "ra_riemann",
            "ifsa",
            "coral",
            "coral_safe",
            "tl_center_scale",
        }:
            acc, kappa, n_fit, extra = _run_signal_fold(
                x=x,
                y=y,
                meta=meta,
                train_idx=train_idx,
                test_idx=test_idx,
                protocol=protocol_cfg,
                cov_cfg=cov_cfg,
                method_name=method_name,
                method_cfg=method_cfg,
                model_name=model_name,
                model_cfg=model_cfg,
                subject_n_jobs=subj_n_jobs,
            )
        else:
            acc, kappa, n_fit, extra = _run_tangent_fold(
                x=x,
                y=y,
                meta=meta,
                classes=classes,
                train_idx=train_idx,
                test_idx=test_idx,
                protocol=protocol_cfg,
                cov_cfg=cov_cfg,
                method_name=method_name,
                method_cfg=method_cfg,
                model_name=model_name,
            )

        runtime = time.perf_counter() - start
        row = {
            "subject": int(target_subject),
            "acc": float(acc),
            "kappa": float(kappa),
            "n_trials_used_for_alignment": int(n_fit),
            "runtime_sec": float(runtime),
        }
        row.update(extra)

        pair = None
        if compute_baseline and baseline_method != method_name:
            if method_name in {"tsa", "tsa_ss"}:
                # baseline = tangent identity (no rotation)
                acc_b, kappa_b, n_fit_b, _ = _run_tangent_fold(
                    x=x,
                    y=y,
                    meta=meta,
                    classes=classes,
                    train_idx=train_idx,
                    test_idx=test_idx,
                    protocol=protocol_cfg,
                    cov_cfg=cov_cfg,
                    method_name="tangent_identity",
                    method_cfg={},
                    model_name=model_name,
                )
                baseline_acc = float(acc_b)
                baseline_kappa = float(kappa_b)
                row["baseline_method"] = "tangent_identity"
                row["baseline_n_trials_used_for_alignment"] = int(n_fit_b)
            else:
                acc_b, kappa_b, n_fit_b, _ = _run_signal_fold(
                    x=x,
                    y=y,
                    meta=meta,
                    train_idx=train_idx,
                    test_idx=test_idx,
                    protocol=protocol_cfg,
                    cov_cfg=cov_cfg,
                    method_name=baseline_method,
                    method_cfg={},
                    model_name=model_name,
                    model_cfg=model_cfg,
                    subject_n_jobs=subj_n_jobs,
                )
                baseline_acc = float(acc_b)
                baseline_kappa = float(kappa_b)
                row["baseline_method"] = baseline_method
                row["baseline_n_trials_used_for_alignment"] = int(n_fit_b)

            row["baseline_acc"] = float(baseline_acc)
            row["baseline_kappa"] = float(baseline_kappa)
            row["neg_transfer"] = bool(row["acc"] < row["baseline_acc"])
            pair = (float(baseline_acc), float(acc))

        if bool(trim_memory):
            _trim_memory()

        return row, pair

    if fold_n_jobs <= 1 or len(folds) <= 1:
        fold_results = [
            _run_one_fold(target_subject, train_idx, test_idx)
            for target_subject, train_idx, test_idx in folds
        ]
    else:
        fold_results = Parallel(n_jobs=min(fold_n_jobs, len(folds)), prefer="threads")(
            delayed(_run_one_fold)(target_subject, train_idx, test_idx)
            for target_subject, train_idx, test_idx in folds
        )

    rows = [row for row, _ in fold_results]
    pairs = [pair for _, pair in fold_results if pair is not None]
    baseline_accs = [p[0] for p in pairs]
    method_accs = [p[1] for p in pairs]

    df = pd.DataFrame(rows)
    neg_transfer_ratio = (
        float(np.mean(df["neg_transfer"])) if "neg_transfer" in df.columns else float("nan")
    )

    stats = None
    if compute_baseline and baseline_method != method_name and baseline_accs:
        stats = paired_wilcoxon_with_effect(np.asarray(baseline_accs), np.asarray(method_accs))

    metric_cols = [
        "spec_var_before",
        "spec_var_after",
        "control_energy",
        "track_error_before",
        "track_error_after",
        "triggered",
        "trigger_tau_eff",
        "ifsa_safety_gate_factor",
        "ifsa_safety_hold",
        "ifsa_safety_score_mode",
        "ifsa_safety_score_target",
        "ifsa_safety_tau_source",
        "ifsa_safety_tau_eff",
        "ifsa_safety_quantile",
        "ifsa_safety_disc_loss",
        "ifsa_safety_disc_loss_tau",
        "ifsa_safety_low_score_mult",
        "ifsa_safety_low_tau_eff",
        "ifsa_safety_low_hold",
        "ifsa_safety_disc_scale_tau",
        "ifsa_safety_disc_scale_max_trials_per_class",
        "ifsa_safety_disc_scale_factor",
        "ifsa_safety_disc_scale_triggered",
        "principal_angle_deg_mean",
        "subspace_similarity_mean",
    ]
    for col in metric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    summary = {
        "subject": "__summary__",
        "acc": float(df["acc"].mean()),
        "acc_std": float(df["acc"].std(ddof=1)) if df.shape[0] > 1 else 0.0,
        "kappa": float(df["kappa"].mean()),
        "kappa_std": float(df["kappa"].std(ddof=1)) if df.shape[0] > 1 else 0.0,
        "runtime_sec": float(df["runtime_sec"].sum()),
        "n_trials_used_for_alignment": int(df["n_trials_used_for_alignment"].sum()),
        "neg_transfer_ratio": neg_transfer_ratio,
    }
    for col in metric_cols:
        if col in df.columns:
            summary[f"{col}_mean"] = float(df[col].mean())
    if stats is not None:
        summary.update(
            {
                "wilcoxon_p": stats.p_value,
                "wilcoxon_p_holm": stats.p_value_holm,
                "effect_rank_biserial": stats.effect_rank_biserial,
            }
        )

    df = pd.concat([df, pd.DataFrame([summary])], ignore_index=True)
    return df
