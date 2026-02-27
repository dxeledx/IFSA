from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import rankdata, wilcoxon


@dataclass(frozen=True)
class PairedStats:
    p_value: float
    p_value_holm: float
    effect_rank_biserial: float


def holm_adjust(p_values: list[float]) -> list[float]:
    m = len(p_values)
    order = np.argsort(p_values)
    adjusted = np.empty(m, dtype=float)
    running_max = 0.0
    for i, idx in enumerate(order):
        factor = m - i
        running_max = max(running_max, min(1.0, factor * float(p_values[idx])))
        adjusted[idx] = running_max
    return adjusted.tolist()


def _paired_wilcoxon_effect(baseline: np.ndarray, method: np.ndarray) -> tuple[float, float]:
    baseline = np.asarray(baseline, dtype=float)
    method = np.asarray(method, dtype=float)
    if baseline.shape != method.shape:
        raise ValueError("baseline and method must have same shape")

    diff = method - baseline
    nonzero = diff != 0
    diff_nz = diff[nonzero]
    if diff_nz.size == 0:
        return 1.0, 0.0

    stat = wilcoxon(method[nonzero], baseline[nonzero], zero_method="wilcox", correction=False)

    ranks = rankdata(np.abs(diff_nz))
    w_pos = float(np.sum(ranks[diff_nz > 0]))
    w_neg = float(np.sum(ranks[diff_nz < 0]))
    effect = (w_pos - w_neg) / max(1e-12, (w_pos + w_neg))

    return float(stat.pvalue), float(effect)


def paired_wilcoxon_many(baseline: np.ndarray, methods: list[np.ndarray]) -> list[PairedStats]:
    p_values = []
    effects = []
    for method in methods:
        p, e = _paired_wilcoxon_effect(baseline, method)
        p_values.append(float(p))
        effects.append(float(e))

    adjusted = holm_adjust(p_values)
    return [
        PairedStats(
            p_value=float(p_values[i]),
            p_value_holm=float(adjusted[i]),
            effect_rank_biserial=float(effects[i]),
        )
        for i in range(len(p_values))
    ]


def paired_wilcoxon_with_effect(baseline: np.ndarray, method: np.ndarray) -> PairedStats:
    p, e = _paired_wilcoxon_effect(baseline, method)
    p_adj = holm_adjust([float(p)])[0]

    return PairedStats(
        p_value=float(p),
        p_value_holm=float(p_adj),
        effect_rank_biserial=float(e),
    )
