from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
from joblib import Parallel, delayed, parallel
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

    n_jobs_env = os.environ.get("EAPP_COV_N_JOBS", "")
    try:
        n_jobs = int(n_jobs_env) if n_jobs_env else 1
    except ValueError:
        n_jobs = 1
    n_jobs = max(1, n_jobs)

    # Avoid nested parallelism: outer joblib loops already spread work across
    # folds/subjects; spawning per-trial threads inside those workers leads to
    # oversubscription and can slow down or bloat memory.
    try:
        backend, _ = parallel.get_active_backend()
        nesting = int(getattr(backend, "nesting_level", 0) or 0)
        if nesting > 0:
            n_jobs = 1
    except Exception:
        # Never fail covariance computation due to backend introspection.
        pass

    if n_jobs <= 1 or x.shape[0] <= 1:
        return np.stack([fn(trial, cfg.epsilon) for trial in x], axis=0)

    max_jobs = min(int(n_jobs), int(x.shape[0]))
    cov_list = Parallel(n_jobs=max_jobs, prefer="threads")(
        delayed(fn)(trial, cfg.epsilon) for trial in x
    )
    return np.stack(cov_list, axis=0)
