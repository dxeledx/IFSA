import numpy as np
import pytest

from eapp.alignment.tsa import TSAConfig, align_tangent_space


def _random_spd_batch(n: int, c: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    covs = []
    for _ in range(n):
        a = rng.standard_normal((c, c))
        spd = a @ a.T
        spd.flat[:: c + 1] += 1.0
        covs.append(spd)
    return np.stack(covs, axis=0)


def test_tsa_supervised_requires_labels():
    source_covs = _random_spd_batch(10, 4, seed=0)
    target_covs = _random_spd_batch(6, 4, seed=1)
    source_y = np.array([0, 1] * 5)
    classes = np.array([0, 1])

    with pytest.raises(ValueError, match="requires target labels"):
        align_tangent_space(
            source_covs=source_covs,
            source_y=source_y,
            source_classes=classes,
            target_covs=target_covs,
            target_covs_fit=target_covs,
            target_y_for_anchors=None,
            cfg=TSAConfig(anchor_strategy="supervised_target"),
            eps=1e-12,
        )
