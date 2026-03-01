# Architecture

## High-level Flow
1) **Compose config** (Hydra) → `src/eapp/run.py::_compose_cfg()`
2) **Load dataset** (MOABB + cached `.npz`) → `src/eapp/datasets/moabb_dataset.py::load_moabb_dataset()`
3) **Run LOSO evaluation** → `src/eapp/eval/loso.py::run_loso()`
4) **Write per-subject CSV** → `results/tables/{dataset}__{variant}__{model}__{tdu}.csv`
5) **Generate summaries / matrices / stats**:
   - `src/eapp/report.py` → `summary__{dataset}__{tdu}.csv`
   - `src/eapp/report_matrix.py` → `matrix__{model}__*.csv`
   - `src/eapp/report_pairwise.py` → `pairwise__*.csv` (Wilcoxon + Holm, effect sizes, NTR)

## Core Abstractions

### Protocol (target usage)
Target data usage is controlled by:
- `configs/protocol/loso.yaml`
- `src/eapp/eval/loso.py::ProtocolConfig`
- `_target_alignment_subset()` chooses which unlabeled target subset is allowed:
  - `transductive_unlabeled_all`
  - `online_prefix_unlabeled`
  - `few_shot_labeled` (if enabled)

### Alignment Methods
All “signal” alignment methods implement a common pattern:
- `fit(x_subject)` → compute an alignment matrix (often SPD-related)
- `transform(x)` → apply matrix to signals or covariances

Implemented under `src/eapp/alignment/`:
- `ea.py` (Euclidean alignment)
- `ra.py` / `ra_riemann.py` (Riemannian alignment variants)
- `coral.py`
- `ifsa.py` (Incremental / target-guided with safety clutch)
- `tsa.py` / `tsa_ss.py` (tangent-space pipelines)

### Models
- CSP+LDA: `src/eapp/models/csp_lda.py`
- MDM: `src/eapp/models/mdm.py`
- Tangent-LDA: `src/eapp/models/tangent_lda.py`

### SPD Utilities
Central SPD math lives in:
- `src/eapp/utils/spd.py`

This provides stable log/exp/sqrt/invsqrt for SPD matrices and helpers like `sym(...)`.

## Evaluation Concurrency & Memory Model
- LOSO fold evaluation lives in `src/eapp/eval/loso.py`.
- Two levels of possible parallelism:
  - **Fold-parallelism** (`runtime.n_jobs`): can be memory-dangerous on large datasets
    because each fold slices near-full `x_train`.
  - **Within-fold parallelism** (safer): e.g. covariance computation via `EAPP_COV_N_JOBS`
    (see `src/eapp/representation/covariance.py`), or per-subject alignment via
    `eval.subject_n_jobs` (small subject count, cheap).
- For large MOABB datasets (PhysioNetMI), recommended is:
  - `runtime.n_jobs=1` (sequential folds)
  - `EAPP_COV_N_JOBS≈#physical_cores`
  - `eval.trim_memory=true` to reduce RSS growth.

