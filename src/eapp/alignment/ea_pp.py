from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from eapp.representation.covariance import CovarianceConfig, compute_covariances
from eapp.utils.spd import (
    Eigendecomp,
    clamp_eigenvalues,
    eigh_sym,
    expm_sym,
    invsqrtm_spd,
    log_eigvals_spd,
    logm_spd,
    sym,
)


@dataclass(frozen=True)
class EAPPMetrics:
    spec_var_before: float
    spec_var_after: float
    control_energy: float


@dataclass(frozen=True)
class EAPPConfig:
    lambda_mean: float
    lambda_spec: float
    lambda_u: float
    k_steps: int
    lr: float
    ema_alpha: float


def _shrink_log_spectrum(decomp: Eigendecomp, strength: float) -> np.ndarray:
    """Shrink log-eigen spectrum towards its mean (reduce variance)."""
    values = clamp_eigenvalues(decomp.values, 1e-30)
    log_vals = np.log(values)
    mean_log = float(np.mean(log_vals))
    log_new = mean_log + (1.0 - strength) * (log_vals - mean_log)
    return decomp.vectors @ np.diag(np.exp(log_new)) @ decomp.vectors.T


class EAPPSignalAligner:
    def __init__(self, cov_cfg: CovarianceConfig, cfg: EAPPConfig):
        self.cov_cfg = cov_cfg
        self.cfg = cfg
        self.matrix: np.ndarray | None = None
        self.metrics: EAPPMetrics | None = None

    def fit(self, x: np.ndarray) -> EAPPSignalAligner:
        covs = compute_covariances(x, self.cov_cfg)
        mean_cov = np.mean(covs, axis=0)
        a = invsqrtm_spd(mean_cov, eps=self.cov_cfg.epsilon)

        if self.cfg.k_steps <= 0:
            covs_aligned = np.stack([a @ cov @ a.T for cov in covs], axis=0)
            spec_var_before = float(
                np.mean([np.var(log_eigvals_spd(cov, self.cov_cfg.epsilon)) for cov in covs])
            )
            spec_var_after = float(
                np.mean(
                    [np.var(log_eigvals_spd(cov, self.cov_cfg.epsilon)) for cov in covs_aligned]
                )
            )
            control_energy = float(np.linalg.norm(a - np.eye(a.shape[0]), ord="fro"))
            self.matrix = a
            self.metrics = EAPPMetrics(
                spec_var_before=spec_var_before,
                spec_var_after=spec_var_after,
                control_energy=control_energy,
            )
            return self

        identity = np.eye(a.shape[0], dtype=float)
        a_prev = a
        for _ in range(int(self.cfg.k_steps)):
            covs_aligned = np.stack([a_prev @ cov @ a_prev.T for cov in covs], axis=0)
            mean_aligned = np.mean(covs_aligned, axis=0)

            # mean correction in log-domain (fractional whitening)
            error = logm_spd(mean_aligned, eps=self.cov_cfg.epsilon)
            update = expm_sym(-self.cfg.lr * float(self.cfg.lambda_mean) * error)
            a_new = update @ a_prev

            # Stabilize spectrum of A itself (heuristic but CPU-friendly).
            # - lambda_spec: reduce eigen spread
            # - lambda_u: pull towards identity (energy constraint)
            a_new = sym(a_new)
            decomp = eigh_sym(a_new)
            strength_spec = max(0.0, min(1.0, self.cfg.lr * float(self.cfg.lambda_spec)))
            a_new = _shrink_log_spectrum(decomp, strength=strength_spec)

            if self.cfg.lambda_u > 0:
                decomp_u = eigh_sym(a_new)
                values = clamp_eigenvalues(decomp_u.values, 1e-30)
                log_vals = np.log(values)
                log_vals = (1.0 - self.cfg.lr * float(self.cfg.lambda_u)) * log_vals
                a_new = decomp_u.vectors @ np.diag(np.exp(log_vals)) @ decomp_u.vectors.T

            # EMA for stability (SPD convex combo).
            alpha = float(self.cfg.ema_alpha)
            a_prev = sym((1.0 - alpha) * a_prev + alpha * a_new)

        self.matrix = a_prev

        covs_aligned = np.stack([self.matrix @ cov @ self.matrix.T for cov in covs], axis=0)
        spec_var_before = float(
            np.mean([np.var(log_eigvals_spd(cov, self.cov_cfg.epsilon)) for cov in covs])
        )
        spec_var_after = float(
            np.mean([np.var(log_eigvals_spd(cov, self.cov_cfg.epsilon)) for cov in covs_aligned])
        )
        control_energy = float(np.linalg.norm(self.matrix - identity, ord="fro"))

        self.metrics = EAPPMetrics(
            spec_var_before=spec_var_before,
            spec_var_after=spec_var_after,
            control_energy=control_energy,
        )
        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        if self.matrix is None:
            raise RuntimeError("EAPPSignalAligner not fit")
        return np.einsum("ij,njt->nit", self.matrix, x)
