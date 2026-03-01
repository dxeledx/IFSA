# Integrations

## Overview
This repo is mostly “offline” research code. External integrations are primarily:
- Dataset download + caching (MOABB/MNE)
- Remote CPU server workflow (SSH + rsync + tmux)
- Optional plotting stack for paper figures

## Dataset / EEG Tooling
- **MOABB**: dataset access + paradigm (`src/eapp/datasets/moabb_dataset.py`)
  - Downloads raw data on first run (remote/local).
  - Cached as `.npz` + metadata CSV under `data/cache/` (path configurable via `runtime.cache_dir`).
- **MNE**: epoching/filtering/resampling inside MOABB pipelines
  - For PhysioNetMI, resampling is often forced for stability: `preprocess.resample=160`

## Remote Execution (RLserver)
- Remote host mapping is recorded in `codex.remote.toml` (canonical local↔remote mapping).
- Sync code (WAN-safe; avoids large dirs): `scripts/remote/rl_sync.sh`
  - Excludes: `.venv/`, `data/`, `runs/`, `results/`
  - Uses `rsync --filter=':- .gitignore'` and a `--max-size=100m` cap.
- Run long experiments in tmux: `scripts/remote/rl_run_tmux.sh`
- Fetch back small artifacts (tables/figures/logs): `scripts/remote/rl_fetch_results.sh`

## Plotting / Figures (optional dependency)
- Most report scripts try to import `matplotlib` (guarded with try/except).
- Paper figure scripts live under `scripts/analysis/`:
  - `scripts/analysis/plot_cov_distance_heatmap.py`
  - `scripts/analysis/plot_cov_tsne_fold.py`
  - `scripts/analysis/plot_online_prefix_sweep.py`

## OS / Environment Constraints
- macOS may have restricted Python builds where importing native wheels fails.
  - When that happens, prefer running reports/plots on `RLserver-ex` and fetching outputs.

