from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def plot_baseline_vs_method(df: pd.DataFrame, out_path: Path) -> None:
    if "baseline_acc" not in df.columns:
        return
    df_plot = df[df["subject"] != "__summary__"].copy()
    if df_plot.empty:
        return

    rows = []
    for _, row in df_plot.iterrows():
        rows.append({"kind": "baseline", "acc": row["baseline_acc"]})
        rows.append({"kind": "method", "acc": row["acc"]})
    tidy = pd.DataFrame(rows)

    plt.figure(figsize=(5, 4))
    sns.barplot(data=tidy, x="kind", y="acc", errorbar="sd")
    plt.ylim(0.0, 1.0)
    plt.title("Baseline vs Method (Acc)")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def plot_paired_subject_lines(df: pd.DataFrame, out_path: Path) -> None:
    if "baseline_acc" not in df.columns:
        return
    df_plot = df[df["subject"] != "__summary__"].copy()
    if df_plot.empty:
        return

    plt.figure(figsize=(6, 4))
    for _, row in df_plot.iterrows():
        plt.plot([0, 1], [row["baseline_acc"], row["acc"]], marker="o", alpha=0.7)
    plt.xticks([0, 1], ["baseline", "method"])
    plt.ylim(0.0, 1.0)
    plt.title("Subject-wise paired Acc")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def plot_log_eig_violin(df: pd.DataFrame, out_path: Path) -> None:
    """Violin plot for log-eigenvalues before/after alignment.

    Expects columns: stage ∈ {"before","after"}, log_eig (float).
    """
    if df.empty:
        return
    if not {"stage", "log_eig"} <= set(df.columns):
        return

    plt.figure(figsize=(6, 4))
    sns.violinplot(data=df, x="stage", y="log_eig", inner="quartile", cut=0)
    plt.title("log-eig distribution (before vs after)")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()
