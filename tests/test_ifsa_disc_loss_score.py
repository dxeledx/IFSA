import numpy as np

from eapp.eval.loso import _ifsa_disc_separation_score_from_covs


def _random_spd(dim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = rng.standard_normal((dim, dim))
    spd = a @ a.T
    spd.flat[:: dim + 1] += 1.0
    return spd


def test_ifsa_disc_separation_disc_loss_detects_collapse():
    dim = 6
    eps = 1e-6
    a = _random_spd(dim, seed=0)
    b = _random_spd(dim, seed=1)

    covs_before = np.stack([a] * 4 + [b] * 4, axis=0)
    y = np.asarray([0] * 4 + [1] * 4, dtype=int)

    disc_before = _ifsa_disc_separation_score_from_covs(
        covs_before, y, mean_mode="logeuclid", eps=eps
    )
    assert np.isfinite(disc_before)
    assert disc_before > 1e-6

    disc_after_same = _ifsa_disc_separation_score_from_covs(
        covs_before, y, mean_mode="logeuclid", eps=eps
    )
    disc_loss_same = max(0.0, 1.0 - float(disc_after_same) / max(1e-12, float(disc_before)))
    assert np.isfinite(disc_loss_same)
    assert disc_loss_same < 1e-8

    covs_after_collapsed = np.stack([a] * 8, axis=0)
    disc_after_collapsed = _ifsa_disc_separation_score_from_covs(
        covs_after_collapsed, y, mean_mode="logeuclid", eps=eps
    )
    disc_loss_collapsed = max(
        0.0, 1.0 - float(disc_after_collapsed) / max(1e-12, float(disc_before))
    )
    assert np.isfinite(disc_loss_collapsed)
    assert disc_loss_collapsed > 0.5

