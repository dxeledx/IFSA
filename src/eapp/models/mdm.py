from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pyriemann.classification import MDM


@dataclass(frozen=True)
class MDMConfig:
    metric: str


class MDMClassifier:
    def __init__(self, cfg: MDMConfig):
        self.cfg = cfg
        self._clf: MDM | None = None

    def fit(self, covs: np.ndarray, y: np.ndarray) -> MDMClassifier:
        clf = MDM(metric=self.cfg.metric)
        clf.fit(covs, y)
        self._clf = clf
        return self

    def predict(self, covs: np.ndarray) -> np.ndarray:
        if self._clf is None:
            raise RuntimeError("MDMClassifier not fit")
        return self._clf.predict(covs)

