# Repo File Structure

This repo is a reproducibility-first research infra for cross-subject EEG alignment
(EA / RA / TSA + IFSA / TSA-SS).

## Top-level

- `README.md`: quickstart + remote workflow + reporting commands.
- `pyproject.toml`: package metadata and dev tool configs (ruff/pytest).
- `requirements.txt`, `requirements-dev.txt`: Python deps (runtime / dev).
- `codex.remote.toml`: local↔remote path mapping used by `scripts/remote/*`.
- `src/`: Python package source code (`eapp`).
- `configs/`: Hydra configs (datasets / methods / experiments / protocols / runtime).
- `scripts/`: helper scripts for running/analysis and remote execution.
- `tests/`: unit tests and regression tests.
- `tasks/`: experiment snapshots / iteration notes (not runtime-critical).

## Artifact directories (gitignored by default)

- `runs/`: Hydra output dirs (configs/logs). Only `.gitkeep` is committed.
- `results/`: tables/figures exported by reporting scripts. Only `.gitkeep` is committed.
- `data/`: local dataset cache (downloaded datasets / precomputed features).

## `src/eapp/` (core code)

- `run.py`: main Hydra entry (`python -m eapp.run experiment=...`).
- `alignment/`: alignment methods (`ea.py`, `ra.py`, `tsa.py`, `ifsa.py`, etc.).
- `datasets/`: dataset wrappers and loaders.
- `models/`: decoding models (e.g., CSP/LDA variants).
- `eval/`: evaluation protocols (e.g., LOSO).
- `report.py`, `report_matrix.py`, `report_pairwise.py`: paper-friendly aggregation & plots.
- `utils/`, `representation/`: shared utilities and feature/geometry helpers.

## `configs/` (Hydra config layout)

- `config.yaml`: base config.
- `dataset/`, `method/`, `model/`, `protocol/`, `preprocess/`, `runtime/`: composable config groups.
- `experiment/`: experiment presets referenced by `experiment=...`.

## `scripts/remote/` (CPU server workflow)

- `rl_sync.sh`: rsync code to remote (WAN-safe; does not sync `data/`).
- `rl_setup.sh`: create venv + install deps on remote.
- `rl_run_tmux.sh`: run commands in a detached `tmux` session on remote.
- `rl_fetch_results.sh`: pull back small artifacts (tables/figures/logs).

