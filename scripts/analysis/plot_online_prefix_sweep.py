#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

try:  # Optional dependency (may fail in restricted Python builds).
    import matplotlib.pyplot as plt  # type: ignore
except Exception:  # pragma: no cover
    plt = None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Plot online-prefix stability curves from summary tables."
    )
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--dataset", default="bci_iv_2a")
    parser.add_argument("--model", default="csp_lda")
    parser.add_argument(
        "--bases",
        default="ea,coral,ifsa_final_v1",
        help="Comma-separated base variant names, expects variants like '<base>_prefix20'.",
    )
    args = parser.parse_args(argv)

    results_dir = Path(args.results_dir)
    summary_path = results_dir / "tables" / f"summary__{args.dataset}__online_prefix_unlabeled.csv"
    if not summary_path.exists():
        raise SystemExit(
            f"Missing {summary_path}. Generate it first, e.g.:\n"
            f"  python -m eapp.report runtime.results_dir={results_dir} dataset={args.dataset} "
            f"protocol.target_data_usage=online_prefix_unlabeled"
        )

    df = pd.read_csv(summary_path)
    df = df[(df["model"] == str(args.model))].copy()
    if df.empty:
        raise SystemExit(f"No rows for model={args.model} in {summary_path}")

    bases = [b.strip() for b in str(args.bases).split(",") if b.strip()]
    pat = re.compile(r"_prefix(?P<n>\\d+)$")

    rows = []
    for b in bases:
        sub = df[df["variant"].astype(str).str.startswith(f"{b}_prefix")].copy()
        for _, r in sub.iterrows():
            m = pat.search(str(r["variant"]))
            if not m:
                continue
            rows.append(
                {
                    "base": b,
                    "prefix_n_trials": int(m.group("n")),
                    "acc_mean": float(r["acc_mean"]),
                    "neg_transfer_ratio": float(r.get("neg_transfer_ratio", float("nan"))),
                }
            )

    if not rows:
        raise SystemExit(
            "No prefix-sweep variants found. Expected variants like 'ea_prefix20', "
            "'coral_prefix20', 'ifsa_final_v1_prefix20'."
        )

    df_plot = pd.DataFrame(rows)
    df_plot = df_plot.sort_values(["base", "prefix_n_trials"]).reset_index(drop=True)

    if plt is None:
        print(df_plot.to_string(index=False))
        return

    out_dir = results_dir / "figures" / "paper"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"online_prefix_sweep__{args.dataset}__{args.model}.png"

    plt.figure(figsize=(6.5, 4.2))
    for base, grp in df_plot.groupby("base"):
        plt.plot(
            grp["prefix_n_trials"].to_numpy(),
            grp["acc_mean"].to_numpy(),
            marker="o",
            label=base,
        )
    plt.xlabel("online_prefix_n_trials")
    plt.ylabel("acc_mean")
    plt.ylim(0.0, 1.0)
    plt.title(f"{args.dataset} online-prefix sweep ({args.model})")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close()

    print(f"[done] plot: {out_path}")


if __name__ == "__main__":
    main()

