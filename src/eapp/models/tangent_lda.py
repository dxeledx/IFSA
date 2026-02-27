from __future__ import annotations

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis


class TangentLDAClassifier:
    def __init__(self):
        self._clf: LinearDiscriminantAnalysis | None = None

    def fit(self, z: np.ndarray, y: np.ndarray) -> TangentLDAClassifier:
        clf = LinearDiscriminantAnalysis()
        clf.fit(z, y)
        self._clf = clf
        return self

    def predict(self, z: np.ndarray) -> np.ndarray:
        if self._clf is None:
            raise RuntimeError("TangentLDAClassifier not fit")
        return self._clf.predict(z)

