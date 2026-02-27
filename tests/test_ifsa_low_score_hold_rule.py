import numpy as np

from eapp.eval.loso import _ifsa_low_score_hold_decision


def test_ifsa_low_score_hold_triggers_below_threshold():
    hold, low_tau = _ifsa_low_score_hold_decision(
        score_target=0.83,
        tau_eff=1.0,
        safety_low_score_mult=0.85,
    )
    assert hold == 1
    assert np.isfinite(low_tau)
    assert np.isclose(low_tau, 0.85)


def test_ifsa_low_score_hold_not_triggered_above_threshold():
    hold, low_tau = _ifsa_low_score_hold_decision(
        score_target=0.86,
        tau_eff=1.0,
        safety_low_score_mult=0.85,
    )
    assert hold == 0
    assert np.isfinite(low_tau)
    assert np.isclose(low_tau, 0.85)


def test_ifsa_low_score_hold_disabled_returns_nan():
    hold, low_tau = _ifsa_low_score_hold_decision(
        score_target=0.1,
        tau_eff=1.0,
        safety_low_score_mult=0.0,
    )
    assert hold == 0
    assert np.isnan(low_tau)


def test_ifsa_low_score_hold_clamps_multiplier():
    hold, low_tau = _ifsa_low_score_hold_decision(
        score_target=0.9,
        tau_eff=1.0,
        safety_low_score_mult=2.0,
    )
    assert hold == 1
    assert np.isclose(low_tau, 1.0)


def test_ifsa_low_score_hold_nan_inputs_no_trigger():
    hold, low_tau = _ifsa_low_score_hold_decision(
        score_target=float("nan"),
        tau_eff=1.0,
        safety_low_score_mult=0.85,
    )
    assert hold == 0
    assert np.isnan(low_tau)
