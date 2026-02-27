import numpy as np

from eapp.alignment.coral import coral_matrix
from eapp.utils.spd import sym


def _random_spd(dim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = rng.standard_normal((dim, dim))
    spd = a @ a.T
    spd.flat[:: dim + 1] += 1.0
    return spd


def test_coral_matrix_matches_target_covariance():
    dim = 6
    eps = 1e-6
    ms = _random_spd(dim, seed=0)
    mt = _random_spd(dim, seed=1)

    a = coral_matrix(source_mean_cov=ms, target_mean_cov=mt, eps=eps)

    out = a @ ms @ a.T
    assert np.isfinite(a).all()
    assert np.isfinite(out).all()
    assert np.all(np.linalg.eigvalsh(sym(out)) > 0)
    assert np.allclose(out, mt, atol=1e-6, rtol=1e-6)

