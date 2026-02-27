import numpy as np

from eapp.alignment.ifsa import IFSAConfig, IFSASignalAligner
from eapp.representation.covariance import CovarianceConfig, compute_covariances
from eapp.utils.spd import invsqrtm_spd, log_euclidean_mean, logm_spd, sym


def _random_spd(dim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = rng.standard_normal((dim, dim))
    spd = a @ a.T
    spd.flat[:: dim + 1] += 1.0
    return spd


def _mean_cov(covs: np.ndarray, *, mode: str, eps: float) -> np.ndarray:
    if mode == "arith":
        return sym(np.mean(covs, axis=0))
    if mode == "logeuclid":
        return log_euclidean_mean(covs, eps=eps)
    raise ValueError(f"Unknown mean_mode={mode!r}")


def test_ifsa_euclid_thrust_matches_desired_congruence():
    rng = np.random.default_rng(123)
    n_trials, n_channels, n_times = 12, 6, 96
    x = rng.standard_normal((n_trials, n_channels, n_times))

    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    ref = _random_spd(n_channels, seed=1)
    target_mean_cov = _random_spd(n_channels, seed=2)

    cfg = IFSAConfig(
        lambda_track=4.0,
        lambda_spec=0.0,
        lambda_damp=0.0,
        cov_trace_norm=False,
        cov_shrink_alpha=0.0,
        cov_log_spec_shrink=0.0,
        mean_mode="logeuclid",
        target_beta=1.0,
        desired_shrink_alpha=0.0,
        desired_log_spec_shrink=0.0,
        lambda_u=0.0,
        k_steps=1,
        lr=0.3,
        ema_alpha=1.0,
        thrust_mode="euclid",
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

    aligner = IFSASignalAligner(
        cov_cfg,
        cfg,
        reference_cov=ref,
        target_mean_cov=target_mean_cov,
    ).fit(x)

    a = aligner.matrix
    assert a is not None
    assert np.isfinite(a).all()

    covs = compute_covariances(x, cov_cfg)
    mean_cov = _mean_cov(covs, mode=cfg.mean_mode, eps=cov_cfg.epsilon)
    mean_cov_aligned = sym(a @ mean_cov @ a.T)

    w = invsqrtm_spd(target_mean_cov, eps=cov_cfg.epsilon)
    dist_before = float(
        np.linalg.norm(
            logm_spd(sym(w @ mean_cov @ w), eps=cov_cfg.epsilon),
            ord="fro",
        )
    )
    dist_after = float(
        np.linalg.norm(
            logm_spd(sym(w @ mean_cov_aligned @ w), eps=cov_cfg.epsilon),
            ord="fro",
        )
    )
    assert dist_after < dist_before
    assert dist_after < 1e-6

    m = aligner.metrics
    assert m is not None
    assert np.isfinite(m.spec_var_before)
    assert np.isfinite(m.spec_var_after)
    assert np.isfinite(m.control_energy)
    assert np.isfinite(m.track_error_before)
    assert np.isfinite(m.track_error_after)

