import numpy as np
import pandas as pd
import pytest

import eapp.eval.loso as loso
from eapp.eval.loso import ProtocolConfig
from eapp.representation.covariance import CovarianceConfig
from eapp.utils.spd import sym


def _random_spd(dim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = rng.standard_normal((dim, dim))
    spd = a @ a.T
    spd.flat[:: dim + 1] += 1.0
    return spd


def test_tl_center_scale_runs_and_outputs_spd():
    pytest.importorskip("pyriemann", exc_type=ImportError)

    from pyriemann.transfer import TLCenter, TLScale, encode_domains

    eps = 1e-8
    dim = 5

    x = np.stack([_random_spd(dim, seed=i) for i in range(12)], axis=0)
    y = np.zeros(x.shape[0], dtype=int)
    domains = np.array(["1"] * 6 + ["2"] * 6, dtype=object)

    _, y_enc = encode_domains(x, y, domains)

    center = TLCenter(target_domain="2", metric="riemann")
    x_centered = center.fit_transform(x, y_enc)

    scale = TLScale(target_domain="2", final_dispersion=1.0, centered_data=True, metric="riemann")
    x_scaled = scale.fit_transform(x_centered, y_enc)

    assert np.isfinite(x_scaled).all()
    for cov in x_scaled:
        assert np.all(np.linalg.eigvalsh(sym(cov)) > eps)


def test_tl_center_scale_requires_mdm():
    rng = np.random.default_rng(0)
    x = rng.standard_normal((8, 4, 32))
    y = np.array([0, 1] * 4)
    subjects = np.array([1] * 4 + [2] * 4)
    meta = pd.DataFrame({"subject": subjects})

    train_idx = np.where(subjects == 1)[0]
    test_idx = np.where(subjects == 2)[0]

    protocol = ProtocolConfig(
        target_data_usage="transductive_unlabeled_all",
        online_prefix_n_trials=3,
        few_shot_n_trials=2,
    )
    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)

    with pytest.raises(ValueError, match="model=mdm"):
        loso._run_signal_fold(
            x=x,
            y=y,
            meta=meta,
            train_idx=train_idx,
            test_idx=test_idx,
            protocol=protocol,
            cov_cfg=cov_cfg,
            method_name="tl_center_scale",
            method_cfg={},
            model_name="csp_lda",
            model_cfg={"n_components": 2, "reg": "ledoit_wolf"},
        )
