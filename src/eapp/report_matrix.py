from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def _parse_summary_name(path: Path) -> tuple[str, str] | None:
    # expected: summary__{dataset}__{target_data_usage}.csv
    if not path.name.startswith("summary__") or path.suffix != ".csv":
        return None
    parts = path.stem.split("__")
    if len(parts) < 3:
        return None
    dataset = parts[1]
    target_data_usage = "__".join(parts[2:])
    return dataset, target_data_usage


def _tdu_sort_key(tdu: str) -> tuple[int, str]:
    priority = {
        "transductive_unlabeled_all": 0,
        "online_prefix_unlabeled": 10,
        "few_shot_labeled": 20,
    }
    return priority.get(tdu, 100), tdu


def _method_sort_key(method: str) -> tuple[int, str]:
    priority = {
        "identity": 0,
        "ea": 10,
        "ra": 20,
        "ra_riemann": 21,
        "coral": 25,
        "coral_safe": 26,
        "tl_center_scale": 27,
        "ifsa": 30,
        "tsa": 50,
        "tsa_ss": 60,
    }
    return priority.get(method, 100), method


def _read_summaries(tables_dir: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in sorted(tables_dir.glob("summary__*.csv")):
        parsed = _parse_summary_name(path)
        if parsed is None:
            continue
        dataset_from_name, tdu_from_name = parsed
        df = pd.read_csv(path)
        if "dataset" not in df.columns:
            df["dataset"] = dataset_from_name
        if "target_data_usage" not in df.columns:
            df["target_data_usage"] = tdu_from_name
        frames.append(df)

    if not frames:
        raise SystemExit(f"No summary tables found under {tables_dir}")
    return pd.concat(frames, ignore_index=True)


def _best_rows_by_method(df: pd.DataFrame) -> pd.DataFrame:
    # df is one (dataset, tdu, model) subset.
    df = df.copy()
    df["acc_mean"] = pd.to_numeric(df["acc_mean"], errors="coerce")
    df["acc_std"] = pd.to_numeric(df["acc_std"], errors="coerce")
    df["neg_transfer_ratio"] = pd.to_numeric(df.get("neg_transfer_ratio", np.nan), errors="coerce")
    idx = df.groupby("method")["acc_mean"].idxmax()
    return df.loc[idx].reset_index(drop=True)


def _make_setting_label(dataset: str, target_data_usage: str) -> str:
    return f"{dataset}__{target_data_usage}"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate per-setting summaries into report matrices."
    )
    parser.add_argument(
        "--results-dir",
        default="results",
        help="Results directory (default: results).",
    )
    parser.add_argument(
        "--models",
        default="",
        help="Comma-separated models to include (default: all models in summaries).",
    )
    parser.add_argument(
        "--datasets",
        default="",
        help="Comma-separated datasets to include (default: all datasets in summaries).",
    )
    parser.add_argument(
        "--target-data-usages",
        default="",
        help="Comma-separated target_data_usage values to include (default: all in summaries).",
    )
    parser.add_argument(
        "--methods",
        default="",
        help="Comma-separated methods to include (default: all methods in summaries).",
    )
    args = parser.parse_args(argv)

    results_dir = Path(args.results_dir)
    tables_dir = results_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    df = _read_summaries(tables_dir)
    if not {"dataset", "target_data_usage", "model", "method", "variant", "acc_mean"}.issubset(
        df.columns
    ):
        raise SystemExit(
            "Summary tables missing required columns; regenerate via `python -m eapp.report`."
        )

    if args.datasets:
        keep = {s.strip() for s in args.datasets.split(",") if s.strip()}
        df = df[df["dataset"].isin(sorted(keep))]
    if args.target_data_usages:
        keep = {s.strip() for s in args.target_data_usages.split(",") if s.strip()}
        df = df[df["target_data_usage"].isin(sorted(keep))]
    if args.models:
        keep = {s.strip() for s in args.models.split(",") if s.strip()}
        df = df[df["model"].isin(sorted(keep))]
    if args.methods:
        keep = {s.strip() for s in args.methods.split(",") if s.strip()}
        df = df[df["method"].isin(sorted(keep))]

    if df.empty:
        raise SystemExit("No rows left after filtering.")

    settings = sorted(
        {(str(r.dataset), str(r.target_data_usage)) for r in df.itertuples(index=False)},
        key=lambda x: (x[0], _tdu_sort_key(x[1])),
    )
    setting_labels = [_make_setting_label(d, t) for d, t in settings]

    for model in sorted({str(m) for m in df["model"].unique().tolist()}):
        df_model = df[df["model"] == model]
        if df_model.empty:
            continue

        methods: set[str] = set()
        acc: dict[str, dict[str, float]] = {}
        ntr: dict[str, dict[str, float]] = {}
        variant: dict[str, dict[str, str]] = {}

        for dataset, tdu in settings:
            df_setting = df_model[
                (df_model["dataset"] == dataset) & (df_model["target_data_usage"] == tdu)
            ]
            if df_setting.empty:
                continue

            best = _best_rows_by_method(df_setting)
            label = _make_setting_label(dataset, tdu)
            for row in best.itertuples(index=False):
                method = str(row.method)
                methods.add(method)
                acc.setdefault(method, {})[label] = float(row.acc_mean)
                ntr.setdefault(method, {})[label] = float(
                    getattr(row, "neg_transfer_ratio", np.nan)
                )
                variant.setdefault(method, {})[label] = str(row.variant)

        if not methods:
            continue

        method_list = sorted(methods, key=_method_sort_key)

        acc_df = pd.DataFrame.from_dict(acc, orient="index").reindex(
            index=method_list, columns=setting_labels
        )
        ntr_df = pd.DataFrame.from_dict(ntr, orient="index").reindex(
            index=method_list, columns=setting_labels
        )
        var_df = pd.DataFrame.from_dict(variant, orient="index").reindex(
            index=method_list, columns=setting_labels
        )

        out_acc = tables_dir / f"matrix__{model}__acc_mean.csv"
        out_ntr = tables_dir / f"matrix__{model}__neg_transfer_ratio.csv"
        out_var = tables_dir / f"matrix__{model}__best_variant.csv"

        acc_df.to_csv(out_acc, float_format="%.6f")
        ntr_df.to_csv(out_ntr, float_format="%.6f")
        var_df.to_csv(out_var, index=True)

        print(f"[done] matrix: {out_acc}")
        print(f"[done] matrix: {out_ntr}")
        print(f"[done] matrix: {out_var}")


if __name__ == "__main__":
    main()
