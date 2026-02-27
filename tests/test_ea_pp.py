import numpy as np

from eapp.alignment.ea import EASignalAligner
from eapp.alignment.ea_pp import EAPPConfig, EAPPSignalAligner
from eapp.representation.covariance import CovarianceConfig


def test_ea_pp_k0_degenerates_to_ea():
    rng = np.random.default_rng(0)
    x = rng.standard_normal((12, 6, 50))
    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)

    ea = EASignalAligner(cov_cfg).fit(x)
    ea_pp = EAPPSignalAligner(
        cov_cfg,
        EAPPConfig(
            lambda_mean=1.0,
            lambda_spec=1.0,
            lambda_u=1.0,
            k_steps=0,
            lr=0.5,
            ema_alpha=0.9,
        ),
    ).fit(x)

    assert np.allclose(ea.matrix, ea_pp.matrix, atol=1e-10)

