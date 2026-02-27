from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def sym(matrix: np.ndarray) -> np.ndarray:
    return (matrix + matrix.T) / 2.0


@dataclass(frozen=True)
class Eigendecomp:
    vectors: np.ndarray
    values: np.ndarray


def eigh_sym(matrix: np.ndarray) -> Eigendecomp:
    values, vectors = np.linalg.eigh(sym(matrix))
    return Eigendecomp(vectors=vectors, values=values)


def clamp_eigenvalues(values: np.ndarray, eps: float) -> np.ndarray:
    return np.maximum(values, eps)


def invsqrtm_spd(matrix: np.ndarray, eps: float) -> np.ndarray:
    decomp = eigh_sym(matrix)
    values = clamp_eigenvalues(decomp.values, eps)
    inv_sqrt = np.diag(1.0 / np.sqrt(values))
    return decomp.vectors @ inv_sqrt @ decomp.vectors.T


def sqrtm_spd(matrix: np.ndarray, eps: float) -> np.ndarray:
    decomp = eigh_sym(matrix)
    values = clamp_eigenvalues(decomp.values, eps)
    sqrt = np.diag(np.sqrt(values))
    return decomp.vectors @ sqrt @ decomp.vectors.T


def logm_spd(matrix: np.ndarray, eps: float) -> np.ndarray:
    decomp = eigh_sym(matrix)
    values = clamp_eigenvalues(decomp.values, eps)
    log_values = np.diag(np.log(values))
    return decomp.vectors @ log_values @ decomp.vectors.T


def expm_sym(matrix: np.ndarray) -> np.ndarray:
    decomp = eigh_sym(matrix)
    exp_values = np.diag(np.exp(decomp.values))
    return decomp.vectors @ exp_values @ decomp.vectors.T


def log_eigvals_spd(matrix: np.ndarray, eps: float) -> np.ndarray:
    values = clamp_eigenvalues(np.linalg.eigvalsh(sym(matrix)), eps)
    return np.log(values)


def log_euclidean_mean(covs: np.ndarray, eps: float) -> np.ndarray:
    """Log-Euclidean mean of SPD matrices (fast, stable)."""
    logs = np.stack([logm_spd(cov, eps) for cov in covs], axis=0)
    return expm_sym(np.mean(logs, axis=0))

