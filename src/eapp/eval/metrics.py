from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import accuracy_score, cohen_kappa_score


@dataclass(frozen=True)
class FoldMetrics:
    acc: float
    kappa: float


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> FoldMetrics:
    return FoldMetrics(
        acc=float(accuracy_score(y_true, y_pred)),
        kappa=float(cohen_kappa_score(y_true, y_pred)),
    )

