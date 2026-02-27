from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

from eapp.representation.tangent import tangent_space_identity
from eapp.utils.spd import invsqrtm_spd, log_euclidean_mean


@dataclass(frozen=True)
class TSAConfig:
    anchor_strategy: str  # pseudo_label | supervised_target


@dataclass(frozen=True)
class TSAResult:
    source_z: np.ndarray
    source_y: np.ndarray
    target_z: np.ndarray
    target_z_aligned: np.ndarray
    rotation: np.ndarray
    pseudo_label_acc: float | None


def _recenter_matrix(covs: np.ndarray, eps: float) -> np.ndarray:
    mean_cov = log_euclidean_mean(covs, eps=eps)
    return invsqrtm_spd(mean_cov, eps=eps)


def _apply_recenter(covs: np.ndarray, recenter: np.ndarray) -> np.ndarray:
    return np.stack([recenter @ cov @ recenter.T for cov in covs], axis=0)


def _procrustes_rotation(source_anchors: np.ndarray, target_anchors: np.ndarray) -> np.ndarray:
    cross = source_anchors @ target_anchors.T
    u, _, vt = np.linalg.svd(cross, full_matrices=False)
    return u @ vt


def _compute_class_anchors(z: np.ndarray, y: np.ndarray, classes: np.ndarray) -> np.ndarray:
    d = z.shape[1]
    anchors = np.zeros((d, classes.shape[0]), dtype=float)
    for idx, c in enumerate(classes):
        mask = y == c
        if not np.any(mask):
            continue
        anchors[:, idx] = np.mean(z[mask], axis=0)
    return anchors


def align_tangent_space(
    *,
    source_covs: np.ndarray,
    source_y: np.ndarray,
    source_classes: np.ndarray,
    target_covs: np.ndarray,
    target_covs_fit: np.ndarray | None,
    target_y_for_anchors: np.ndarray | None,
    cfg: TSAConfig,
    eps: float,
) -> TSAResult:
    """TSA MVP: recenter both domains, tangent-map at I, then rotate target via Procrustes."""
    source_recenter = _recenter_matrix(source_covs, eps=eps)
    source_covs_c = _apply_recenter(source_covs, source_recenter)

    fit_covs = target_covs if target_covs_fit is None else target_covs_fit
    target_recenter = _recenter_matrix(fit_covs, eps=eps)
    target_covs_fit_c = _apply_recenter(fit_covs, target_recenter)
    target_covs_all_c = _apply_recenter(target_covs, target_recenter)

    source_z = tangent_space_identity(source_covs_c, eps=eps)
    target_z_fit = tangent_space_identity(target_covs_fit_c, eps=eps)
    target_z_all = tangent_space_identity(target_covs_all_c, eps=eps)

    pseudo_label_acc: float | None = None
    if cfg.anchor_strategy == "pseudo_label":
        clf = LinearDiscriminantAnalysis()
        clf.fit(source_z, source_y)
        target_y_hat = clf.predict(target_z_fit)
        target_y_for_anchors = target_y_hat
    elif cfg.anchor_strategy == "supervised_target":
        if target_y_for_anchors is None:
            raise ValueError(
                "TSA anchor_strategy=supervised_target requires target labels (few-shot mode)"
            )
    else:
        raise ValueError(f"Unknown TSA anchor_strategy={cfg.anchor_strategy}")

    source_anchors = _compute_class_anchors(source_z, source_y, source_classes)
    target_anchors = _compute_class_anchors(target_z_fit, target_y_for_anchors, source_classes)

    rotation = _procrustes_rotation(source_anchors, target_anchors)
    target_z_aligned = (rotation @ target_z_all.T).T

    return TSAResult(
        source_z=source_z,
        source_y=source_y,
        target_z=target_z_all,
        target_z_aligned=target_z_aligned,
        rotation=rotation,
        pseudo_label_acc=pseudo_label_acc,
    )
