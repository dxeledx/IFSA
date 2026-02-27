from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from eapp.alignment.tsa import TSAConfig, align_tangent_space


@dataclass(frozen=True)
class TSASSConfig:
    anchor_strategy: str
    k_dim: int
    subspace_lock_weight: float


@dataclass(frozen=True)
class TSASSResult:
    source_z: np.ndarray
    source_y: np.ndarray
    target_z_aligned: np.ndarray
    rotation: np.ndarray
    principal_angle_deg_mean: float
    subspace_similarity_mean: float


def _stable_subspace_from_source_means(
    z: np.ndarray, subjects: np.ndarray, k_dim: int
) -> np.ndarray:
    unique = np.unique(subjects)
    means = np.stack([np.mean(z[subjects == s], axis=0) for s in unique], axis=0)  # (n_subj, d)
    means = means - means.mean(axis=0, keepdims=True)

    # Cov across subjects; stable directions = smallest variance directions.
    cov = (means.T @ means) / max(1, means.shape[0] - 1)
    vals, vecs = np.linalg.eigh((cov + cov.T) / 2.0)
    order = np.argsort(vals)  # ascending
    k = int(min(k_dim, vecs.shape[1]))
    basis = vecs[:, order[:k]]

    # Orthonormal (numerical safety)
    q, _ = np.linalg.qr(basis)
    return q[:, :k]


def _principal_angles_deg(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    # Compute cosines via SVD of A^T B (both orthonormal).
    u, s, vt = np.linalg.svd(a.T @ b, full_matrices=False)
    s = np.clip(s, 0.0, 1.0)
    angles = np.degrees(np.arccos(s))
    return float(np.mean(angles)), float(np.mean(s))


def align_tangent_space_with_stable_subspace(
    *,
    source_covs: np.ndarray,
    source_y: np.ndarray,
    source_classes: np.ndarray,
    source_subjects: np.ndarray,
    target_covs: np.ndarray,
    target_covs_fit: np.ndarray | None,
    target_y_for_anchors: np.ndarray | None,
    cfg: TSASSConfig,
    eps: float,
) -> TSASSResult:
    tsa_res = align_tangent_space(
        source_covs=source_covs,
        source_y=source_y,
        source_classes=source_classes,
        target_covs=target_covs,
        target_covs_fit=target_covs_fit,
        target_y_for_anchors=target_y_for_anchors,
        cfg=TSAConfig(anchor_strategy=cfg.anchor_strategy),
        eps=eps,
    )

    basis = _stable_subspace_from_source_means(tsa_res.source_z, source_subjects, cfg.k_dim)
    projection = basis @ basis.T

    z_orig = tsa_res.target_z
    z_rot = tsa_res.target_z_aligned

    identity = np.eye(projection.shape[0])
    # Lock stable subspace to original, rotate only unstable part.
    z_lock = (projection @ z_orig.T).T + ((identity - projection) @ z_rot.T).T
    w = float(cfg.subspace_lock_weight)
    target_z_final = (1.0 - w) * z_rot + w * z_lock

    angle_mean, sim_mean = _principal_angles_deg(basis, tsa_res.rotation @ basis)

    return TSASSResult(
        source_z=tsa_res.source_z,
        source_y=tsa_res.source_y,
        target_z_aligned=target_z_final,
        rotation=tsa_res.rotation,
        principal_angle_deg_mean=angle_mean,
        subspace_similarity_mean=sim_mean,
    )
