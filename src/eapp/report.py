from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from hydra import compose, initialize_config_dir
from hydra.core.global_hydra import GlobalHydra

from eapp.eval.stats import holm_adjust, paired_wilcoxon_with_effect

try:  # Optional dependency (may fail in restricted Python builds).
    import matplotlib.pyplot as plt  # type: ignore
except Exception:  # pragma: no cover
    plt = None


@dataclass(frozen=True)
class ResultTable:
    path: Path
    dataset: str
    target_data_usage: str
    model: str
    method: str
    variant: str
    subject_acc: dict[int, float]
    acc_mean: float
    acc_std: float
    runtime_sec_sum: float
    baseline_method: str | None
    subject_baseline_acc: dict[int, float] | None


def _parse_table_name(path: Path) -> tuple[str, str, str, str] | None:
    # expected: {dataset}__{variant}__{model}__{target_data_usage}.csv
    parts = path.stem.split("__")
    if len(parts) < 4:
        return None
    dataset = parts[0]
    target_data_usage = parts[-1]
    model = parts[-2]
    variant = "__".join(parts[1:-2])
    return dataset, variant, model, target_data_usage


def _read_result_table(path: Path) -> ResultTable | None:
    parsed = _parse_table_name(path)
    if parsed is None:
        return None
    dataset, variant_from_name, model_from_name, tdu_from_name = parsed

    df = pd.read_csv(path)
    if "subject" not in df.columns or "acc" not in df.columns:
        return None

    df_sub = df[df["subject"] != "__summary__"].copy()
    if df_sub.empty:
        return None
    df_sub["subject"] = df_sub["subject"].astype(int)

    subject_acc = dict(
        zip(df_sub["subject"].tolist(), df_sub["acc"].astype(float).tolist(), strict=True)
    )
    acc_mean = float(np.mean(list(subject_acc.values())))
    acc_std = float(np.std(list(subject_acc.values()), ddof=1)) if len(subject_acc) > 1 else 0.0
    runtime_sec_sum = (
        float(df_sub["runtime_sec"].astype(float).sum()) if "runtime_sec" in df_sub else 0.0
    )

    method = str(df["method"].iloc[0]) if "method" in df.columns else variant_from_name
    model = str(df["model"].iloc[0]) if "model" in df.columns else model_from_name
    target_data_usage = (
        str(df["target_data_usage"].iloc[0]) if "target_data_usage" in df.columns else tdu_from_name
    )
    variant = str(df["variant"].iloc[0]) if "variant" in df.columns else variant_from_name

    baseline_method = (
        str(df["baseline_method"].iloc[0]) if "baseline_method" in df.columns else None
    )
    subject_baseline_acc = None
    if "baseline_acc" in df_sub.columns:
        subject_baseline_acc = dict(
            zip(
                df_sub["subject"].tolist(),
                df_sub["baseline_acc"].astype(float).tolist(),
                strict=True,
            )
        )

    return ResultTable(
        path=path,
        dataset=dataset,
        target_data_usage=target_data_usage,
        model=model,
        method=method,
        variant=variant,
        subject_acc=subject_acc,
        acc_mean=acc_mean,
        acc_std=acc_std,
        runtime_sec_sum=runtime_sec_sum,
        baseline_method=baseline_method,
        subject_baseline_acc=subject_baseline_acc,
    )


def _compose_cfg(overrides: list[str]) -> object:
    config_dir = (Path(__file__).resolve().parents[2] / "configs").as_posix()
    if GlobalHydra.instance().is_initialized():
        GlobalHydra.instance().clear()
    with initialize_config_dir(version_base=None, config_dir=config_dir):
        return compose(config_name="config", overrides=overrides)


def _variant_sort_key(variant: str) -> tuple[int, str]:
    priority = {
        "identity": 0,
        "ea": 10,
        "ra": 20,
        "ra_riemann": 21,
        "coral": 22,
        "tl_center_scale": 23,
        "ifsa": 25,
        "ifsa_no_spec": 26,
        "ifsa_no_damp": 27,
        "ifsa_no_energy": 28,
        "ifsa_trigger": 29,
        "tsa": 40,
        "tsa_ss": 41,
        "tangent_identity": 5,
    }
    return priority.get(variant, 100), variant


def _aligned_arrays(
    baseline: dict[int, float], method: dict[int, float]
) -> tuple[np.ndarray, np.ndarray, list[int]]:
    subjects = sorted(set(baseline.keys()) & set(method.keys()))
    b = np.asarray([baseline[s] for s in subjects], dtype=float)
    m = np.asarray([method[s] for s in subjects], dtype=float)
    return b, m, subjects


def _family_vs_baseline(
    *,
    tables: list[ResultTable],
    baseline_variant: str,
    baseline_acc: dict[int, float],
) -> dict[str, dict]:
    rows: dict[str, dict] = {}

    p_values = []
    variants = []
    effects = []
    neg_transfer_ratios = []

    for t in tables:
        if t.variant == baseline_variant:
            continue
        b, m, _ = _aligned_arrays(baseline_acc, t.subject_acc)
        stats = paired_wilcoxon_with_effect(b, m)
        p_values.append(float(stats.p_value))
        effects.append(float(stats.effect_rank_biserial))
        variants.append(t.variant)
        neg_transfer_ratios.append(float(np.mean(m < b)) if b.size else float("nan"))

    p_holm = holm_adjust(p_values) if p_values else []

    for i, v in enumerate(variants):
        rows[v] = {
            "p_value": float(p_values[i]),
            "p_holm": float(p_holm[i]),
            "effect_rank_biserial": float(effects[i]),
            "neg_transfer_ratio": float(neg_transfer_ratios[i]),
        }

    return rows


def main(argv: list[str] | None = None) -> None:
    overrides = sys.argv[1:] if argv is None else argv
    cfg = _compose_cfg(overrides)

    dataset = str(cfg.dataset.name)
    target_data_usage = str(cfg.protocol.target_data_usage)
    results_dir = Path(str(cfg.runtime.results_dir))
    tables_dir = results_dir / "tables"
    figs_dir = results_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figs_dir.mkdir(parents=True, exist_ok=True)

    paths = sorted(tables_dir.glob(f"{dataset}__*__*__{target_data_usage}.csv"))
    tables: list[ResultTable] = []
    for p in paths:
        if p.name.startswith("summary__"):
            continue
        if "__base__" in p.name:
            continue
        t = _read_result_table(p)
        if t is not None and t.dataset == dataset and t.target_data_usage == target_data_usage:
            tables.append(t)

    if not tables:
        raise SystemExit(
            f"No tables found under {tables_dir} for dataset={dataset} tdu={target_data_usage}"
        )

    by_model: dict[str, list[ResultTable]] = {}
    for t in tables:
        by_model.setdefault(t.model, []).append(t)

    out_rows: list[dict] = []

    for model, model_tables in sorted(by_model.items()):
        model_tables = sorted(model_tables, key=lambda x: _variant_sort_key(x.variant))

        # Keep only "full" LOSO runs for this model (avoid mixing smoke / partial-subject runs
        # into Holm correction and summary tables).
        max_subjects = max(len(t.subject_acc) for t in model_tables)
        model_tables = [t for t in model_tables if len(t.subject_acc) == max_subjects]

        # ---------- Family 1: vs Identity (or tangent_identity fallback) ----------
        baseline_variant = "identity"
        baseline_acc: dict[int, float] | None = None
        for t in model_tables:
            if t.variant == "identity":
                baseline_acc = t.subject_acc
                break

        if baseline_acc is None:
            # Tangent pipeline uses tangent_identity baseline stored inside each TSA/TSA-SS table.
            for t in model_tables:
                if t.subject_baseline_acc is not None and t.baseline_method is not None:
                    baseline_variant = t.baseline_method
                    baseline_acc = t.subject_baseline_acc
                    break

        family1_stats: dict[str, dict] = {}
        baseline_acc_mean = (
            float(np.mean(list(baseline_acc.values()))) if baseline_acc else float("nan")
        )
        if baseline_acc is not None:
            family1_stats = _family_vs_baseline(
                tables=model_tables, baseline_variant=baseline_variant, baseline_acc=baseline_acc
            )

        # ---------- Family 2: TSA-SS vs TSA ----------
        tsa_acc: dict[int, float] | None = None
        for t in model_tables:
            if t.variant == "tsa":
                tsa_acc = t.subject_acc
                break
        tsa_ss = next((t for t in model_tables if t.variant == "tsa_ss"), None)
        p_vs_tsa: dict[str, dict] = {}
        if tsa_acc is not None and tsa_ss is not None:
            b, m, _ = _aligned_arrays(tsa_acc, tsa_ss.subject_acc)
            stats = paired_wilcoxon_with_effect(b, m)
            p_vs_tsa["tsa_ss"] = {
                "p_vs_tsa": float(stats.p_value),
                "p_holm_vs_tsa": float(holm_adjust([float(stats.p_value)])[0]),
                "effect_vs_tsa": float(stats.effect_rank_biserial),
            }

        for t in model_tables:
            row = {
                "dataset": dataset,
                "target_data_usage": target_data_usage,
                "model": model,
                "method": t.method,
                "variant": t.variant,
                "acc_mean": float(t.acc_mean),
                "acc_std": float(t.acc_std),
                "runtime_sec_sum": float(t.runtime_sec_sum),
                "baseline_variant": baseline_variant if baseline_acc is not None else None,
                "baseline_acc_mean": (
                    baseline_acc_mean if baseline_acc is not None else float("nan")
                ),
                "p_value": float("nan"),
                "p_holm": float("nan"),
                "effect_rank_biserial": float("nan"),
                "neg_transfer_ratio": float("nan"),
                "p_vs_tsa": float("nan"),
                "p_holm_vs_tsa": float("nan"),
                "effect_vs_tsa": float("nan"),
            }

            s1 = family1_stats.get(t.variant)
            if s1 is not None:
                row.update(s1)

            s3 = p_vs_tsa.get(t.variant)
            if s3 is not None:
                row.update(s3)

            out_rows.append(row)

        # ---------- Summary plot per model ----------
        df_model = (
            pd.DataFrame(
                [
                    r
                    for r in out_rows
                    if r["dataset"] == dataset
                    and r["target_data_usage"] == target_data_usage
                    and r["model"] == model
                ]
            )
            .sort_values(by="variant", key=lambda s: s.map(lambda v: _variant_sort_key(str(v))))
            .reset_index(drop=True)
        )

        if plt is not None and not df_model.empty:
            x = np.arange(df_model.shape[0])
            plt.figure(figsize=(max(6.0, 0.55 * df_model.shape[0]), 4))
            plt.bar(
                x,
                df_model["acc_mean"].to_numpy(),
                yerr=df_model["acc_std"].to_numpy(),
                capsize=3,
            )
            plt.xticks(x, df_model["variant"].tolist(), rotation=35, ha="right")
            plt.ylim(0.0, 1.0)
            plt.title(f"{dataset} ({target_data_usage}) - {model}")
            plt.tight_layout()
            out_fig = figs_dir / f"summary__{dataset}__{target_data_usage}__{model}.png"
            plt.savefig(out_fig, dpi=160)
            plt.close()

    df_out = pd.DataFrame(out_rows)
    out_csv = tables_dir / f"summary__{dataset}__{target_data_usage}.csv"
    df_out.to_csv(out_csv, index=False)

    print(f"[done] summary: {out_csv}")


if __name__ == "__main__":
    main()
