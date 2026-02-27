from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from eapp.eval.stats import holm_adjust, paired_wilcoxon_with_effect

try:  # Optional dependency (may fail in restricted Python builds).
    import matplotlib.pyplot as plt  # type: ignore
except Exception:  # pragma: no cover
    plt = None

try:  # Optional dependency (may fail in restricted Python builds).
    import seaborn as sns  # type: ignore
except Exception:  # pragma: no cover
    sns = None


def _read_table_subject_acc(path: Path) -> dict[int, float] | None:
    df = pd.read_csv(path)
    if "subject" not in df.columns or "acc" not in df.columns:
        return None
    df_sub = df[df["subject"] != "__summary__"].copy()
    if df_sub.empty:
        return None
    df_sub["subject"] = df_sub["subject"].astype(int)
    return dict(zip(df_sub["subject"].tolist(), df_sub["acc"].astype(float).tolist(), strict=True))


def _aligned_arrays(
    baseline: dict[int, float], method: dict[int, float]
) -> tuple[np.ndarray, np.ndarray, list[int]]:
    subjects = sorted(set(baseline.keys()) & set(method.keys()))
    b = np.asarray([baseline[s] for s in subjects], dtype=float)
    m = np.asarray([method[s] for s in subjects], dtype=float)
    return b, m, subjects


def _variant_from_filename(path: Path) -> str | None:
    # expected: {dataset}__{variant}__{model}__{target_data_usage}.csv
    parts = path.stem.split("__")
    if len(parts) < 4:
        return None
    return "__".join(parts[1:-2])


def _plot_pairwise(
    df_out: pd.DataFrame,
    *,
    title: str,
    out_path: Path,
) -> None:
    if plt is None or sns is None:
        return
    if df_out.empty:
        return

    df_plot = df_out.copy()
    df_plot["baseline_variant"] = df_plot["baseline_variant"].astype(str)
    df_plot = df_plot.set_index("baseline_variant")

    # A compact heatmap: delta_mean colored, Holm p-value annotated.
    heat = df_plot[["delta_mean"]].copy()
    ann = df_plot["p_holm"].map(lambda x: f"p={x:.3g}" if np.isfinite(x) else "p=nan").to_numpy()
    ann = ann.reshape((-1, 1))

    plt.figure(figsize=(6.0, max(2.0, 0.45 * heat.shape[0])))
    sns.heatmap(
        heat,
        annot=ann,
        fmt="",
        cmap="RdYlGn",
        center=0.0,
        cbar_kws={"label": "Δ acc_mean (target - baseline)"},
    )
    plt.title(title)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=180)
    plt.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Paired (subject-wise) Wilcoxon test: target_variant vs baselines."
    )
    parser.add_argument(
        "--results-dir",
        default="results",
        help="Results directory (default: results).",
    )
    parser.add_argument("--dataset", required=True, help="Dataset name (e.g., bci_iv_2a).")
    parser.add_argument(
        "--target-data-usage",
        required=True,
        help="protocol.target_data_usage (e.g., transductive_unlabeled_all).",
    )
    parser.add_argument("--model", required=True, help="Model name (e.g., csp_lda, tangent_lda).")
    parser.add_argument(
        "--target-variant",
        required=True,
        help="Variant name to test (e.g., ifsa_final_v1).",
    )
    parser.add_argument(
        "--baselines",
        default="ea,ra,ra_riemann,coral,identity,tsa,tsa_ss,tangent_identity",
        help=(
            "Comma-separated baseline variants to compare against "
            "(default includes common baselines)."
        ),
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Disable heatmap plot output.",
    )
    args = parser.parse_args(argv)

    results_dir = Path(args.results_dir)
    tables_dir = results_dir / "tables"
    figs_dir = results_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figs_dir.mkdir(parents=True, exist_ok=True)

    dataset = str(args.dataset)
    tdu = str(args.target_data_usage)
    model = str(args.model)
    target_variant = str(args.target_variant)
    baselines = [b.strip() for b in str(args.baselines).split(",") if b.strip()]

    paths = sorted(tables_dir.glob(f"{dataset}__*__{model}__{tdu}.csv"))
    if not paths:
        raise SystemExit(
            f"No tables found for dataset={dataset} model={model} tdu={tdu} under {tables_dir}"
        )

    by_variant: dict[str, Path] = {}
    for p in paths:
        if p.name.startswith("summary__") or p.name.startswith("pairwise__"):
            continue
        if "__base__" in p.name:
            continue
        variant = _variant_from_filename(p)
        if not variant:
            continue
        # Prefer the first occurrence; avoid surprising overrides if duplicates exist.
        by_variant.setdefault(variant, p)

    if target_variant not in by_variant:
        available = ", ".join(sorted(by_variant.keys()))
        raise SystemExit(
            f"target_variant={target_variant!r} not found for dataset={dataset} "
            f"model={model} tdu={tdu}. Available: {available}"
        )

    target_path = by_variant[target_variant]
    target_acc = _read_table_subject_acc(target_path)
    if target_acc is None:
        raise SystemExit(f"Failed to parse target table: {target_path}")

    rows = []
    p_values = []
    effects = []

    for b in baselines:
        p_b = by_variant.get(b)
        if p_b is None:
            continue
        base_acc = _read_table_subject_acc(p_b)
        if base_acc is None:
            continue
        arr_b, arr_t, subjects = _aligned_arrays(base_acc, target_acc)
        if arr_b.size == 0:
            continue

        stats = paired_wilcoxon_with_effect(arr_b, arr_t)
        p_values.append(float(stats.p_value))
        effects.append(float(stats.effect_rank_biserial))
        rows.append(
            {
                "dataset": dataset,
                "target_data_usage": tdu,
                "model": model,
                "target_variant": target_variant,
                "baseline_variant": b,
                "n_subjects": int(arr_b.size),
                "acc_mean_target": float(np.mean(arr_t)),
                "acc_mean_baseline": float(np.mean(arr_b)),
                "delta_mean": float(np.mean(arr_t - arr_b)),
                "p_value": float(stats.p_value),
                "effect_rank_biserial": float(stats.effect_rank_biserial),
                "neg_transfer_ratio": float(np.mean(arr_t < arr_b)),
            }
        )

    if not rows:
        raise SystemExit("No baseline comparisons could be computed (no matching baseline tables).")

    # Holm correction across baselines in this setting.
    p_holm = holm_adjust(p_values)
    for i, row in enumerate(rows):
        row["p_holm"] = float(p_holm[i])

    df_out = pd.DataFrame(rows).sort_values("delta_mean", ascending=False).reset_index(drop=True)

    out_csv = tables_dir / f"pairwise__{dataset}__{tdu}__{model}__{target_variant}.csv"
    df_out.to_csv(out_csv, index=False)
    print(f"[done] pairwise: {out_csv}")

    if not bool(args.no_plot):
        out_fig = figs_dir / f"pairwise__{dataset}__{tdu}__{model}__{target_variant}.png"
        title = f"{dataset} ({tdu}) - {model}: {target_variant} vs baselines"
        _plot_pairwise(df_out, title=title, out_path=out_fig)
        if out_fig.exists():
            print(f"[done] pairwise plot: {out_fig}")


if __name__ == "__main__":
    main()
