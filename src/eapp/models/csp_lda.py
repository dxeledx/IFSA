from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from mne.decoding import CSP
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis


@dataclass(frozen=True)
class CSPLDAConfig:
    n_components: int
    reg: str | float | None


class CSPLDAClassifier:
    def __init__(self, cfg: CSPLDAConfig):
        self.cfg = cfg
        self._csp: CSP | None = None
        self._clf: LinearDiscriminantAnalysis | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> CSPLDAClassifier:
        csp = CSP(n_components=int(self.cfg.n_components), reg=self.cfg.reg, log=True)
        x_feat = csp.fit_transform(x, y)

        clf = LinearDiscriminantAnalysis()
        clf.fit(x_feat, y)

        self._csp = csp
        self._clf = clf
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        if self._csp is None or self._clf is None:
            raise RuntimeError("CSPLDAClassifier not fit")
        x_feat = self._csp.transform(x)
        return self._clf.predict(x_feat)

