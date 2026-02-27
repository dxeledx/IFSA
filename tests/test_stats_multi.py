import numpy as np

from eapp.eval.stats import holm_adjust, paired_wilcoxon_many


def test_holm_adjust_expected_values():
    p = [0.01, 0.04, 0.03]
    adj = holm_adjust(p)
    assert np.allclose(adj, [0.03, 0.06, 0.06])


def test_paired_wilcoxon_many_matches_holm_adjust():
    rng = np.random.default_rng(0)
    baseline = rng.normal(size=12)
    methods = [baseline + rng.normal(scale=0.1, size=12) for _ in range(4)]

    stats = paired_wilcoxon_many(baseline, methods)
    p_values = [s.p_value for s in stats]
    expected = holm_adjust(p_values)
    got = [s.p_value_holm for s in stats]

    assert np.allclose(got, expected)

