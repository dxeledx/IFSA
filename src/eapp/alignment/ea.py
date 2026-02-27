from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from eapp.representation.covariance import CovarianceConfig, compute_covariances
from eapp.utils.spd import invsqrtm_spd, log_eigvals_spd


@dataclass(frozen=True)
class EAMetrics:
    spec_var_before: float
    spec_var_after: float
    control_energy: float


class EASignalAligner:
    def __init__(self, cov_cfg: CovarianceConfig):
        self.cov_cfg = cov_cfg
        self.matrix: np.ndarray | None = None
        self.metrics: EAMetrics | None = None

    def fit(self, x: np.ndarray) -> EASignalAligner:
        covs = compute_covariances(x, self.cov_cfg)
        mean_cov = np.mean(covs, axis=0)
        a = invsqrtm_spd(mean_cov, eps=self.cov_cfg.epsilon)

        covs_aligned = np.stack([a @ cov @ a.T for cov in covs], axis=0)

        spec_var_before = float(
            np.mean([np.var(log_eigvals_spd(cov, self.cov_cfg.epsilon)) for cov in covs])
        )
        spec_var_after = float(
            np.mean([np.var(log_eigvals_spd(cov, self.cov_cfg.epsilon)) for cov in covs_aligned])
        )
        control_energy = float(np.linalg.norm(a - np.eye(a.shape[0]), ord="fro"))

        self.matrix = a
        self.metrics = EAMetrics(
            spec_var_before=spec_var_before,
            spec_var_after=spec_var_after,
            control_energy=control_energy,
        )
        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        if self.matrix is None:
            raise RuntimeError("EASignalAligner not fit")
        return np.einsum("ij,njt->nit", self.matrix, x)
