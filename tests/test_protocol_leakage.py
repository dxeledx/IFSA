import numpy as np
import pandas as pd

from eapp.eval.loso import ProtocolConfig
from eapp.representation.covariance import CovarianceConfig


def _toy_data(seed: int = 0):
    rng = np.random.default_rng(seed)
    n_trials = 20
    n_channels = 4
    n_times = 32

    x = rng.standard_normal((n_trials, n_channels, n_times))
    y = np.array([0, 1] * (n_trials // 2))
    subjects = np.array([1] * (n_trials // 2) + [2] * (n_trials // 2))
    meta = pd.DataFrame({"subject": subjects})

    train_idx = np.where(subjects == 1)[0]
    test_idx = np.where(subjects == 2)[0]
    classes = np.array([0, 1])
    return x, y, meta, classes, train_idx, test_idx


def test_tsa_unlabeled_never_passes_target_labels(monkeypatch):
    import eapp.eval.loso as loso

    x, y, meta, classes, train_idx, test_idx = _toy_data(seed=1)
    protocol = ProtocolConfig(
        target_data_usage="transductive_unlabeled_all",
        online_prefix_n_trials=3,
        few_shot_n_trials=2,
    )
    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)

    def spy_align_tangent_space(
        *,
        source_covs,
        source_y,
        source_classes,
        target_covs,
        target_covs_fit,
        target_y_for_anchors,
        cfg,
        eps,
    ):
        assert target_y_for_anchors is None
        rng = np.random.default_rng(0)
        return type(
            "Res",
            (),
            {
                "source_z": rng.standard_normal((source_covs.shape[0], 3)),
                "target_z_aligned": rng.standard_normal((target_covs.shape[0], 3)),
            },
        )()

    monkeypatch.setattr(loso, "align_tangent_space", spy_align_tangent_space)

    loso._run_tangent_fold(
        x=x,
        y=y,
        meta=meta,
        classes=classes,
        train_idx=train_idx,
        test_idx=test_idx,
        protocol=protocol,
        cov_cfg=cov_cfg,
        method_name="tsa",
        method_cfg={"anchor_strategy": "pseudo_label"},
        model_name="tangent_lda",
    )


def test_tsa_few_shot_passes_prefix_target_labels(monkeypatch):
    import eapp.eval.loso as loso

    x, y, meta, classes, train_idx, test_idx = _toy_data(seed=2)
    protocol = ProtocolConfig(
        target_data_usage="few_shot_labeled",
        online_prefix_n_trials=3,
        few_shot_n_trials=3,
    )
    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)
    expected = y[test_idx][:3]

    def spy_align_tangent_space(
        *,
        target_y_for_anchors,
        source_covs,
        source_y,
        source_classes,
        target_covs,
        target_covs_fit,
        cfg,
        eps,
    ):
        assert target_y_for_anchors is not None
        assert np.array_equal(target_y_for_anchors, expected)
        rng = np.random.default_rng(0)
        return type(
            "Res",
            (),
            {
                "source_z": rng.standard_normal((source_covs.shape[0], 3)),
                "target_z_aligned": rng.standard_normal((target_covs.shape[0], 3)),
            },
        )()

    monkeypatch.setattr(loso, "align_tangent_space", spy_align_tangent_space)

    loso._run_tangent_fold(
        x=x,
        y=y,
        meta=meta,
        classes=classes,
        train_idx=train_idx,
        test_idx=test_idx,
        protocol=protocol,
        cov_cfg=cov_cfg,
        method_name="tsa",
        method_cfg={"anchor_strategy": "pseudo_label"},
        model_name="tangent_lda",
    )


def test_tsa_ss_unlabeled_never_passes_target_labels(monkeypatch):
    import eapp.eval.loso as loso

    x, y, meta, classes, train_idx, test_idx = _toy_data(seed=3)
    protocol = ProtocolConfig(
        target_data_usage="online_prefix_unlabeled",
        online_prefix_n_trials=5,
        few_shot_n_trials=2,
    )
    cov_cfg = CovarianceConfig(estimator="scm", epsilon=1e-6)

    def spy_align_tsa_ss(
        *,
        target_y_for_anchors,
        source_covs,
        target_covs,
        source_y,
        source_classes,
        source_subjects,
        target_covs_fit,
        cfg,
        eps,
    ):
        assert target_y_for_anchors is None
        rng = np.random.default_rng(0)
        return type(
            "Res",
            (),
            {
                "source_z": rng.standard_normal((source_covs.shape[0], 3)),
                "target_z_aligned": rng.standard_normal((target_covs.shape[0], 3)),
                "principal_angle_deg_mean": 0.0,
                "subspace_similarity_mean": 1.0,
            },
        )()

    monkeypatch.setattr(loso, "align_tangent_space_with_stable_subspace", spy_align_tsa_ss)

    loso._run_tangent_fold(
        x=x,
        y=y,
        meta=meta,
        classes=classes,
        train_idx=train_idx,
        test_idx=test_idx,
        protocol=protocol,
        cov_cfg=cov_cfg,
        method_name="tsa_ss",
        method_cfg={"anchor_strategy": "pseudo_label", "k_dim": 2, "subspace_lock_weight": 1.0},
        model_name="tangent_lda",
    )

