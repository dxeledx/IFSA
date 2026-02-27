import numpy as np
import pytest

from eapp.alignment.ra_riemann import RARiemannSignalAligner
from eapp.representation.covariance import CovarianceConfig
from eapp.utils.spd import sym


def test_ra_riemann_returns_spd_matrix_and_metrics():
    pytest.importorskip("pyriemann", exc_type=ImportError)

    rng = np.random.default_rng(0)
    n_trials, n_channels, n_times = 10, 6, 128
    x = rng.standard_normal((n_trials, n_channels, n_times))

    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    aligner = RARiemannSignalAligner(cov_cfg).fit(x)

    a = aligner.matrix
    assert a is not None
    assert np.allclose(a, a.T, atol=1e-10)
    assert np.isfinite(a).all()
    assert np.all(np.linalg.eigvalsh(sym(a)) > 0)

    m = aligner.metrics
    assert m is not None
    assert np.isfinite(m.spec_var_before)
    assert np.isfinite(m.spec_var_after)
    assert np.isfinite(m.control_energy)
