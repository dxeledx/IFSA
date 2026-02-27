import numpy as np

from eapp.alignment.ifsa import IFSAConfig
from eapp.eval.loso import _ifsa_split_half_stability_score_from_covs
from eapp.representation.covariance import CovarianceConfig


def _random_spd(dim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = rng.standard_normal((dim, dim))
    spd = a @ a.T
    spd.flat[:: dim + 1] += 1.0
    return spd


def _cfg(mean_mode: str) -> IFSAConfig:
    return IFSAConfig(
        lambda_track=1.0,
        lambda_spec=0.0,
        lambda_damp=0.0,
        cov_trace_norm=False,
        cov_shrink_alpha=0.0,
        cov_log_spec_shrink=0.0,
        mean_mode=mean_mode,
        target_beta=1.0,
        desired_shrink_alpha=0.0,
        desired_log_spec_shrink=0.0,
        lambda_u=0.0,
        k_steps=1,
        lr=0.3,
        ema_alpha=1.0,
        thrust_mode="spd",
        a_mix_mode="euclid",
        lambda_disp=0.0,
        disp_scale_min=0.5,
        disp_scale_max=2.0,
        trigger_tau=0.0,
        trigger_mode="fixed",
        trigger_quantile=0.7,
        damp_mode="euclid_ema",
        output_space="reference",
        ref_subject_mean_mode="logeuclid",
    )


def test_ifsa_split_half_score_identical_halves_near_zero():
    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    dim = 6
    base = _random_spd(dim, seed=0)
    covs = np.stack([base] * 6, axis=0)

    score = _ifsa_split_half_stability_score_from_covs(covs, cov_cfg, _cfg(mean_mode="arith"))
    assert np.isfinite(score)
    assert score < 1e-8


def test_ifsa_split_half_score_detects_shift():
    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    dim = 5
    base = _random_spd(dim, seed=1)
    covs = np.stack([base] * 3 + [4.0 * base] * 3, axis=0)

    score = _ifsa_split_half_stability_score_from_covs(covs, cov_cfg, _cfg(mean_mode="arith"))
    assert np.isfinite(score)
    assert score > 0.1


def test_ifsa_split_half_score_small_n_is_inf():
    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    dim = 4
    base = _random_spd(dim, seed=2)
    covs = np.stack([base] * 3, axis=0)

    score = _ifsa_split_half_stability_score_from_covs(covs, cov_cfg, _cfg(mean_mode="logeuclid"))
    assert np.isinf(score)
