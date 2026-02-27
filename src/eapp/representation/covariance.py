from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.covariance import LedoitWolf


@dataclass(frozen=True)
class CovarianceConfig:
    estimator: str
    epsilon: float


def _scm(trial: np.ndarray, epsilon: float) -> np.ndarray:
    x = trial - trial.mean(axis=1, keepdims=True)
    cov = (x @ x.T) / max(1, x.shape[1] - 1)
    cov.flat[:: cov.shape[0] + 1] += float(epsilon)
    return cov


def _ledoit_wolf(trial: np.ndarray, epsilon: float) -> np.ndarray:
    x = trial - trial.mean(axis=1, keepdims=True)
    cov = LedoitWolf().fit(x.T).covariance_
    cov.flat[:: cov.shape[0] + 1] += float(epsilon)
    return cov


def compute_covariances(x: np.ndarray, cfg: CovarianceConfig) -> np.ndarray:
    """Compute per-trial channel covariance.

    Args:
        x: (n_trials, n_channels, n_times)
    """
    if x.ndim != 3:
        raise ValueError(f"Expected x.ndim == 3, got {x.ndim}")

    if cfg.estimator == "scm":
        fn = _scm
    elif cfg.estimator == "ledoit_wolf":
        fn = _ledoit_wolf
    else:
        raise ValueError(f"Unknown covariance.estimator={cfg.estimator}")

    covs = np.stack([fn(trial, cfg.epsilon) for trial in x], axis=0)
    return covs

