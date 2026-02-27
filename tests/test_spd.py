import numpy as np

from eapp.utils.spd import expm_sym, invsqrtm_spd, log_euclidean_mean, logm_spd


def _random_spd(dim: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = rng.standard_normal((dim, dim))
    spd = a @ a.T
    spd.flat[:: dim + 1] += 1.0
    return spd


def test_invsqrtm_whitens():
    a = _random_spd(8, seed=1)
    invsqrt = invsqrtm_spd(a, eps=1e-12)
    eye = invsqrt @ a @ invsqrt.T
    assert np.allclose(eye, np.eye(8), atol=1e-6)


def test_logm_expm_roundtrip():
    a = _random_spd(6, seed=2)
    loga = logm_spd(a, eps=1e-12)
    a2 = expm_sym(loga)
    assert np.allclose(a, a2, atol=1e-6)


def test_log_euclidean_mean_spd():
    covs = np.stack([_random_spd(5, seed=3), _random_spd(5, seed=4)], axis=0)
    mean = log_euclidean_mean(covs, eps=1e-12)
    eig = np.linalg.eigvalsh(mean)
    assert np.all(eig > 0)

