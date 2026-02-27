#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def _read_subject_acc(path: Path) -> pd.Series:
    df = pd.read_csv(path)
    df = df[df["subject"] != "__summary__"].copy()
    if df.empty:
        raise ValueError(f"no subjects in {path}")
    df["subject"] = df["subject"].astype(int)
    df["acc"] = pd.to_numeric(df["acc"], errors="coerce")
    return df.set_index("subject")["acc"].sort_index()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Check determinism: compare per-subject acc between two tables."
    )
    parser.add_argument("csv_a", help="First CSV (results/tables/...).")
    parser.add_argument("csv_b", help="Second CSV (results_seedcheck/tables/...).")
    args = parser.parse_args(argv)

    a = _read_subject_acc(Path(args.csv_a))
    b = _read_subject_acc(Path(args.csv_b))
    idx = a.index.intersection(b.index)
    if idx.empty:
        raise SystemExit("no overlapping subjects")

    diff = (a.loc[idx] - b.loc[idx]).abs()
    max_abs = float(diff.max())
    print("n_subjects:", int(idx.size))
    print("max_abs_diff:", max_abs)
    if not np.isfinite(max_abs):
        raise SystemExit("diff is not finite")


if __name__ == "__main__":
    main()
