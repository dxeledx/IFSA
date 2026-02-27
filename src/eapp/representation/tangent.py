from __future__ import annotations

import math

import numpy as np

from eapp.utils.spd import logm_spd, sym


def sym_to_vec(matrix: np.ndarray) -> np.ndarray:
    """Vectorize a symmetric matrix with sqrt(2) scaling for off-diagonals.

    Output dimension: d = C*(C+1)/2
    """
    matrix = sym(matrix)
    c = matrix.shape[0]
    out = []
    sqrt2 = math.sqrt(2.0)
    for i in range(c):
        out.append(matrix[i, i])
        for j in range(i + 1, c):
            out.append(sqrt2 * matrix[i, j])
    return np.asarray(out, dtype=float)


def tangent_space_identity(covs: np.ndarray, eps: float) -> np.ndarray:
    """Map SPD matrices to tangent space at identity using logm."""
    return np.stack([sym_to_vec(logm_spd(cov, eps)) for cov in covs], axis=0)

