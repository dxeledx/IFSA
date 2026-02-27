import numpy as np

from eapp.alignment.ifsa import IFSAConfig, IFSASignalAligner
from eapp.representation.covariance import CovarianceConfig
from eapp.utils.spd import sym


def _random_spd(dim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = rng.standard_normal((dim, dim))
    spd = a @ a.T
    spd.flat[:: dim + 1] += 1.0
    return spd


def test_ifsa_returns_spd_matrix():
    rng = np.random.default_rng(0)
    n_trials, n_channels, n_times = 8, 6, 64
    x = rng.standard_normal((n_trials, n_channels, n_times))

    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    cfg = IFSAConfig(
        lambda_track=1.0,
        lambda_spec=0.2,
        lambda_damp=0.2,
        cov_trace_norm=False,
        cov_shrink_alpha=0.0,
        cov_log_spec_shrink=0.0,
        mean_mode="arith",
        target_beta=0.0,
        desired_shrink_alpha=0.0,
        desired_log_spec_shrink=0.0,
        lambda_u=0.05,
        k_steps=3,
        lr=0.3,
        ema_alpha=0.8,
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
        ref_subject_mean_mode="arith",
    )
    ref = _random_spd(n_channels, seed=1)
    aligner = IFSASignalAligner(cov_cfg, cfg, reference_cov=ref).fit(x)

    a = aligner.matrix
    assert a is not None
    assert np.allclose(a, a.T, atol=1e-10)
    assert np.isfinite(a).all()
    assert np.all(np.linalg.eigvalsh(sym(a)) > 0)


def test_ifsa_trigger_hold_returns_identity():
    rng = np.random.default_rng(1)
    n_trials, n_channels, n_times = 6, 5, 256
    ref = _random_spd(n_channels, seed=2)
    chol = np.linalg.cholesky(ref)
    x = np.stack(
        [chol @ rng.standard_normal((n_channels, n_times)) for _ in range(n_trials)],
        axis=0,
    )

    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    cfg = IFSAConfig(
        lambda_track=1.0,
        lambda_spec=0.2,
        lambda_damp=0.2,
        cov_trace_norm=False,
        cov_shrink_alpha=0.0,
        cov_log_spec_shrink=0.0,
        mean_mode="arith",
        target_beta=0.0,
        desired_shrink_alpha=0.0,
        desired_log_spec_shrink=0.0,
        lambda_u=0.05,
        k_steps=10,
        lr=0.3,
        ema_alpha=0.8,
        thrust_mode="spd",
        a_mix_mode="euclid",
        lambda_disp=0.0,
        disp_scale_min=0.5,
        disp_scale_max=2.0,
        trigger_tau=1e9,
        trigger_mode="fixed",
        trigger_quantile=0.7,
        damp_mode="euclid_ema",
        output_space="reference",
        ref_subject_mean_mode="arith",
    )
    aligner = IFSASignalAligner(cov_cfg, cfg, reference_cov=ref).fit(x)

    assert aligner.metrics is not None
    assert aligner.metrics.triggered == 0
    assert np.allclose(aligner.matrix, np.eye(n_channels), atol=1e-12)


def test_ifsa_metrics_present():
    rng = np.random.default_rng(2)
    n_trials, n_channels, n_times = 10, 4, 80
    x = rng.standard_normal((n_trials, n_channels, n_times))
    ref = _random_spd(n_channels, seed=3)

    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    cfg = IFSAConfig(
        lambda_track=1.0,
        lambda_spec=0.2,
        lambda_damp=0.2,
        cov_trace_norm=False,
        cov_shrink_alpha=0.0,
        cov_log_spec_shrink=0.0,
        mean_mode="arith",
        target_beta=0.0,
        desired_shrink_alpha=0.0,
        desired_log_spec_shrink=0.0,
        lambda_u=0.05,
        k_steps=2,
        lr=0.3,
        ema_alpha=0.8,
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
        ref_subject_mean_mode="arith",
    )
    aligner = IFSASignalAligner(cov_cfg, cfg, reference_cov=ref).fit(x)

    m = aligner.metrics
    assert m is not None
    assert np.isfinite(m.spec_var_before)
    assert np.isfinite(m.spec_var_after)
    assert np.isfinite(m.control_energy)
    assert np.isfinite(m.track_error_before)
    assert np.isfinite(m.track_error_after)
    assert np.isfinite(m.trigger_tau_eff)
    assert m.triggered in (0, 1)


def test_ifsa_logeuclid_mean_spd():
    rng = np.random.default_rng(3)
    n_trials, n_channels, n_times = 8, 6, 64
    x = rng.standard_normal((n_trials, n_channels, n_times))
    ref = _random_spd(n_channels, seed=4)

    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    cfg = IFSAConfig(
        lambda_track=1.0,
        lambda_spec=0.2,
        lambda_damp=0.2,
        cov_trace_norm=False,
        cov_shrink_alpha=0.1,
        cov_log_spec_shrink=0.0,
        mean_mode="logeuclid",
        target_beta=0.0,
        desired_shrink_alpha=0.0,
        desired_log_spec_shrink=0.0,
        lambda_u=0.05,
        k_steps=3,
        lr=0.3,
        ema_alpha=0.8,
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
    aligner = IFSASignalAligner(cov_cfg, cfg, reference_cov=ref).fit(x)
    a = aligner.matrix
    assert a is not None
    assert np.allclose(a, a.T, atol=1e-10)
    assert np.isfinite(a).all()
    assert np.all(np.linalg.eigvalsh(sym(a)) > 0)


def test_ifsa_log_ema_damping_spd():
    rng = np.random.default_rng(4)
    n_trials, n_channels, n_times = 10, 5, 128
    x = rng.standard_normal((n_trials, n_channels, n_times))
    ref = _random_spd(n_channels, seed=5)

    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    cfg = IFSAConfig(
        lambda_track=1.0,
        lambda_spec=0.2,
        lambda_damp=0.5,
        cov_trace_norm=False,
        cov_shrink_alpha=0.0,
        cov_log_spec_shrink=0.0,
        mean_mode="arith",
        target_beta=0.0,
        desired_shrink_alpha=0.0,
        desired_log_spec_shrink=0.0,
        lambda_u=0.05,
        k_steps=3,
        lr=0.3,
        ema_alpha=0.8,
        thrust_mode="spd",
        a_mix_mode="euclid",
        lambda_disp=0.0,
        disp_scale_min=0.5,
        disp_scale_max=2.0,
        trigger_tau=0.0,
        trigger_mode="fixed",
        trigger_quantile=0.7,
        damp_mode="log_ema",
        output_space="reference",
        ref_subject_mean_mode="arith",
    )
    aligner = IFSASignalAligner(cov_cfg, cfg, reference_cov=ref).fit(x)
    a = aligner.matrix
    assert a is not None
    assert np.allclose(a, a.T, atol=1e-10)
    assert np.isfinite(a).all()
    assert np.all(np.linalg.eigvalsh(sym(a)) > 0)


def test_ifsa_identity_output_spd():
    rng = np.random.default_rng(5)
    n_trials, n_channels, n_times = 10, 6, 80
    x = rng.standard_normal((n_trials, n_channels, n_times))
    ref = _random_spd(n_channels, seed=6)

    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    cfg = IFSAConfig(
        lambda_track=1.0,
        lambda_spec=0.2,
        lambda_damp=0.2,
        cov_trace_norm=False,
        cov_shrink_alpha=0.0,
        cov_log_spec_shrink=0.0,
        mean_mode="arith",
        target_beta=0.0,
        desired_shrink_alpha=0.0,
        desired_log_spec_shrink=0.0,
        lambda_u=0.05,
        k_steps=3,
        lr=0.3,
        ema_alpha=0.8,
        thrust_mode="spd",
        a_mix_mode="euclid",
        lambda_disp=0.0,
        disp_scale_min=0.5,
        disp_scale_max=2.0,
        trigger_tau=0.0,
        trigger_mode="fixed",
        trigger_quantile=0.7,
        damp_mode="euclid_ema",
        output_space="identity",
        ref_subject_mean_mode="arith",
    )
    aligner = IFSASignalAligner(cov_cfg, cfg, reference_cov=ref).fit(x)
    a = aligner.matrix
    assert a is not None
    assert np.allclose(a, a.T, atol=1e-10)
    assert np.isfinite(a).all()
    assert np.all(np.linalg.eigvalsh(sym(a)) > 0)


def test_ifsa_trace_norm_spd():
    rng = np.random.default_rng(6)
    n_trials, n_channels, n_times = 8, 6, 64
    x = rng.standard_normal((n_trials, n_channels, n_times))
    ref = _random_spd(n_channels, seed=7)

    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    cfg = IFSAConfig(
        lambda_track=1.0,
        lambda_spec=0.2,
        lambda_damp=0.2,
        cov_trace_norm=True,
        cov_shrink_alpha=0.0,
        cov_log_spec_shrink=0.0,
        mean_mode="arith",
        target_beta=0.0,
        desired_shrink_alpha=0.0,
        desired_log_spec_shrink=0.0,
        lambda_u=0.05,
        k_steps=3,
        lr=0.3,
        ema_alpha=0.8,
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
        ref_subject_mean_mode="arith",
    )
    aligner = IFSASignalAligner(cov_cfg, cfg, reference_cov=ref).fit(x)
    a = aligner.matrix
    assert a is not None
    assert np.allclose(a, a.T, atol=1e-10)
    assert np.isfinite(a).all()
    assert np.all(np.linalg.eigvalsh(sym(a)) > 0)


def test_ifsa_target_beta_spd():
    rng = np.random.default_rng(7)
    n_trials, n_channels, n_times = 10, 6, 96
    x = rng.standard_normal((n_trials, n_channels, n_times))

    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    ref = _random_spd(n_channels, seed=8)
    target_mean_cov = _random_spd(n_channels, seed=9)

    cfg = IFSAConfig(
        lambda_track=1.0,
        lambda_spec=0.2,
        lambda_damp=0.0,
        cov_trace_norm=False,
        cov_shrink_alpha=0.0,
        cov_log_spec_shrink=0.0,
        mean_mode="logeuclid",
        target_beta=0.5,
        desired_shrink_alpha=0.0,
        desired_log_spec_shrink=0.0,
        lambda_u=0.0,
        k_steps=10,
        lr=0.15,
        ema_alpha=0.8,
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
    aligner = IFSASignalAligner(
        cov_cfg, cfg, reference_cov=ref, target_mean_cov=target_mean_cov
    ).fit(x)
    a = aligner.matrix
    assert a is not None
    assert np.allclose(a, a.T, atol=1e-10)
    assert np.isfinite(a).all()
    assert np.all(np.linalg.eigvalsh(sym(a)) > 0)

    m = aligner.metrics
    assert m is not None
    assert np.isfinite(m.track_error_before)
    assert np.isfinite(m.track_error_after)


def test_ifsa_dispersion_matching_metrics_finite():
    rng = np.random.default_rng(10)
    n_trials, n_channels, n_times = 8, 6, 96
    x = rng.standard_normal((n_trials, n_channels, n_times))

    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    ref = _random_spd(n_channels, seed=12)
    target_mean_cov = _random_spd(n_channels, seed=13)

    cfg = IFSAConfig(
        lambda_track=1.0,
        lambda_spec=0.0,
        lambda_damp=0.0,
        cov_trace_norm=False,
        cov_shrink_alpha=0.0,
        cov_log_spec_shrink=0.0,
        mean_mode="logeuclid",
        target_beta=0.5,
        desired_shrink_alpha=0.0,
        desired_log_spec_shrink=0.0,
        lambda_u=0.0,
        k_steps=3,
        lr=0.3,
        ema_alpha=1.0,
        thrust_mode="spd",
        a_mix_mode="euclid",
        lambda_disp=1.0,
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
        target_dispersion=1.0,
    ).fit(x)
    m = aligner.metrics
    assert m is not None
    assert np.isfinite(m.dispersion_target)
    assert np.isfinite(m.dispersion_before)
    assert np.isfinite(m.dispersion_after)
    assert np.isfinite(m.dispersion_scale_eff)


def test_ifsa_desired_regularization_spd():
    rng = np.random.default_rng(11)
    n_trials, n_channels, n_times = 10, 6, 96
    x = rng.standard_normal((n_trials, n_channels, n_times))

    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    ref = _random_spd(n_channels, seed=14)
    target_mean_cov = _random_spd(n_channels, seed=15)

    cfg = IFSAConfig(
        lambda_track=4.0,
        lambda_spec=0.0,
        lambda_damp=0.0,
        cov_trace_norm=False,
        cov_shrink_alpha=0.0,
        cov_log_spec_shrink=0.0,
        mean_mode="logeuclid",
        target_beta=1.0,
        desired_shrink_alpha=0.1,
        desired_log_spec_shrink=0.2,
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
    aligner = IFSASignalAligner(
        cov_cfg,
        cfg,
        reference_cov=ref,
        target_mean_cov=target_mean_cov,
    ).fit(x)
    a = aligner.matrix
    assert a is not None
    assert np.allclose(a, a.T, atol=1e-10)
    assert np.isfinite(a).all()
    assert np.all(np.linalg.eigvalsh(sym(a)) > 0)


def test_ifsa_log_mix_mode_spd():
    rng = np.random.default_rng(8)
    n_trials, n_channels, n_times = 10, 6, 96
    x = rng.standard_normal((n_trials, n_channels, n_times))

    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    ref = _random_spd(n_channels, seed=10)

    cfg = IFSAConfig(
        lambda_track=1.0,
        lambda_spec=0.2,
        lambda_damp=0.2,
        cov_trace_norm=False,
        cov_shrink_alpha=0.1,
        cov_log_spec_shrink=0.0,
        mean_mode="logeuclid",
        target_beta=0.0,
        desired_shrink_alpha=0.0,
        desired_log_spec_shrink=0.0,
        lambda_u=0.05,
        k_steps=3,
        lr=0.3,
        ema_alpha=0.8,
        thrust_mode="spd",
        a_mix_mode="log",
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
    aligner = IFSASignalAligner(cov_cfg, cfg, reference_cov=ref).fit(x)
    a = aligner.matrix
    assert a is not None
    assert np.allclose(a, a.T, atol=1e-10)
    assert np.isfinite(a).all()
    assert np.all(np.linalg.eigvalsh(sym(a)) > 0)


def test_ifsa_cov_log_spec_shrink_spd():
    rng = np.random.default_rng(9)
    n_trials, n_channels, n_times = 10, 6, 96
    x = rng.standard_normal((n_trials, n_channels, n_times))

    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    ref = _random_spd(n_channels, seed=11)

    cfg = IFSAConfig(
        lambda_track=1.0,
        lambda_spec=0.2,
        lambda_damp=0.2,
        cov_trace_norm=False,
        cov_shrink_alpha=0.0,
        cov_log_spec_shrink=0.2,
        mean_mode="logeuclid",
        target_beta=0.0,
        desired_shrink_alpha=0.0,
        desired_log_spec_shrink=0.0,
        lambda_u=0.05,
        k_steps=3,
        lr=0.3,
        ema_alpha=0.8,
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
    aligner = IFSASignalAligner(cov_cfg, cfg, reference_cov=ref).fit(x)
    a = aligner.matrix
    assert a is not None
    assert np.allclose(a, a.T, atol=1e-10)
    assert np.isfinite(a).all()
    assert np.all(np.linalg.eigvalsh(sym(a)) > 0)
