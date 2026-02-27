from __future__ import annotations

import numpy as np


class IdentitySignalAligner:
    def __init__(self, n_channels: int):
        self.matrix = np.eye(n_channels, dtype=float)

    def transform(self, x: np.ndarray) -> np.ndarray:
        return x

