# Stack

## Overview
- Primary language: **Python 3.10+** (remote `RLserver-ex` pinned to 3.10.12).
- Core focus: cross-subject EEG alignment experiments (EA / RA / CORAL / IFSA / TSA / TSA-SS).
- Configuration: **Hydra** (`configs/` + `python -m eapp.run ...` overrides).
- Data loading: **MOABB** + **MNE** (`src/eapp/datasets/moabb_dataset.py`).

## Key Dependencies
- Numeric / ML: `numpy`, `scipy`, `scikit-learn`, `joblib`
- Tables: `pandas`
- EEG: `mne`, `moabb`
- Riemann/SPD tooling: `pyriemann` + internal SPD utilities (`src/eapp/utils/spd.py`)
- Config: `hydra-core`, `omegaconf`
- Plotting (optional): `matplotlib`, `seaborn` (`src/eapp/eval/plots.py`, `src/eapp/report.py`)

Pinned versions are in:
- `requirements.txt`
- `requirements-dev.txt`
- `pyproject.toml`

## CLI Entry Points (modules)
- Run experiments: `python -m eapp.run ...` (`src/eapp/run.py`)
- Per-setting summary: `python -m eapp.report ...` (`src/eapp/report.py`)
- Cross-setting matrix: `python -m eapp.report_matrix ...` (`src/eapp/report_matrix.py`)
- Pairwise stats: `python -m eapp.report_pairwise ...` (`src/eapp/report_pairwise.py`)

## Execution Model
- Evaluation protocol: LOSO (leave-one-subject-out), implemented in `src/eapp/eval/loso.py`.
- Two pipelines:
  - **Signal pipeline**: align signals → CSP+LDA / MDM
  - **Tangent pipeline**: tangent-space features → tangent-LDA (`src/eapp/representation/tangent.py`)

## Reproducibility / Determinism Controls
- Seeds: `configs/runtime/default.yaml` (`runtime.seed`)
- Remote “single-thread BLAS” convention:
  - `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1`
- Long runs via tmux on RL: `scripts/remote/rl_run_tmux.sh`
- Memory-safety knobs (added for large datasets like PhysioNetMI):
  - `eval.trim_memory=true` (fold-level GC + `malloc_trim`)
  - `EAPP_COV_N_JOBS=<N>` to parallelize covariance computation safely (no fold-parallelism)

## Common Commands
- Local setup: see `README.md`
- Quick smoke run:
  - `python -m eapp.run experiment=smoke`
- Remote workflow:
  - `./scripts/remote/rl_sync.sh RLserver-ex`
  - `./scripts/remote/rl_setup.sh RLserver-ex`
  - `./scripts/remote/rl_run_tmux.sh RLserver-ex <label> "<cmd>"`
  - `./scripts/remote/rl_fetch_results.sh RLserver-ex`

