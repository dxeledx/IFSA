# Structure

## Top-level Layout
- `src/eapp/`: main Python package
- `configs/`: Hydra configuration tree
- `scripts/remote/`: RLserver workflow scripts (sync/setup/run/fetch)
- `scripts/analysis/`: paper/diagnostic figures (heatmaps, t-SNE, prefix sweeps)
- `tests/`: pytest unit tests (math + leakage + method contracts)
- `data/`: MOABB caches / downloads (**gitignored**)
- `runs/`: hydra run dirs (**gitignored**, keeps `runs/.gitkeep`)
- `results/`: tables/figures (**gitignored**, keeps `.gitkeep` markers)
- `tasks/`: frozen experiment snapshots and notes (small artifacts only)

## `src/eapp/` Modules
- `src/eapp/run.py`: main experiment runner (Hydra compose → dataset → LOSO → write CSV/plots)
- `src/eapp/eval/loso.py`: LOSO fold loop + per-fold method/model execution
- `src/eapp/datasets/moabb_dataset.py`: cached dataset loader (`data/cache/*.npz`)
- `src/eapp/alignment/*`: alignment methods (EA/RA/CORAL/IFSA/TSA…)
- `src/eapp/models/*`: classifiers and feature pipelines
- `src/eapp/representation/*`: covariance + tangent representations
- `src/eapp/utils/spd.py`: SPD math primitives
- `src/eapp/report*.py`: summary/matrix/pairwise reporting tools

## `configs/` Tree (Hydra)
- `configs/config.yaml`: root defaults + `eval.*` knobs
- `configs/dataset/*.yaml`: dataset definition (MOABB class, events, subjects)
- `configs/preprocess/*.yaml`: bandpass/time window/resample/EOG drop + covariance estimator
- `configs/protocol/*.yaml`: target-data-usage protocol settings
- `configs/method/*.yaml`: method hyperparameters (EA/RA/CORAL/IFSA…)
- `configs/model/*.yaml`: model hyperparameters (CSP+LDA, tangent-LDA…)
- `configs/experiment/*.yaml`: named experiment variants (paper-ready)

## Remote Workflow Scripts
- `scripts/remote/rl_sync.sh`: rsync code to RLserver (WAN-safe filters)
- `scripts/remote/rl_setup.sh`: create `.venv` and install deps on RLserver
- `scripts/remote/rl_run_tmux.sh`: run a command in a detached tmux session (logs to `runs/*.log`)
- `scripts/remote/rl_fetch_results.sh`: pull back `results/tables/` + small figures/logs
- Dataset-specific drivers (examples):
  - `scripts/remote/rl_run_physionet_mi_final_v2_trans.sh`
  - `scripts/remote/physionet_mi_final_v2_trans_inner.sh`

