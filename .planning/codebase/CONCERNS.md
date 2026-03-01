# Concerns / Risks

## 1) Memory blow-ups on large datasets (PhysioNetMI)
**Symptom:** RSS grows until the server becomes unresponsive / reboots.

**Root cause (typical):**
- Fold-parallelism (`runtime.n_jobs > 1`) in LOSO can create multiple large `x_train = x[train_idx]`
  slices simultaneously (each is near “full dataset” sized for large MOABB datasets).
- Some safety diagnostics previously materialized additional aligned copies (e.g. `x_train_candidate`),
  effectively doubling memory pressure.

**Mitigation (current codebase):**
- Prefer fold-sequential:
  - `runtime.n_jobs=1`
- Parallelize only “local” computations:
  - Covariance compute: `EAPP_COV_N_JOBS=<N>` (threads) in `src/eapp/representation/covariance.py`
  - (Optional) per-subject aligner fit: `eval.subject_n_jobs` (small subject count)
- Enable trimming between folds:
  - `eval.trim_memory=true` → `gc.collect()` + `malloc_trim(0)` (Linux/glibc best effort)

## 2) Nested parallelism
If BLAS libraries are not pinned to 1 thread, combining:
- joblib threads
- sklearn / numpy BLAS
can lead to oversubscription and unstable performance.

Mitigation: export
`OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1`.

## 3) Riemann mean convergence warnings
`pyriemann` may warn “Convergence not reached” on some subjects/runs.
This can affect RA-Riemann variants and tangent-space baselines.

Mitigation:
- treat warnings as diagnostic (not necessarily fatal)
- consider increasing max-iter / adjusting tolerance if it becomes performance-critical

## 4) Determinism across machines
- Different Python/numpy wheels can produce tiny numeric diffs.
- macOS environment may block native wheels (pandas/matplotlib issues), forcing report/plot to run
  on RLserver and fetched back.

Mitigation:
- pin versions in `requirements.txt`
- run “paper tables + figures” on a single controlled environment (RLserver)
- use per-subject paired tests (Wilcoxon) which are robust to tiny float drift

## 5) Experiment artifact hygiene
- `results/` and `runs/` are gitignored by design (`.gitignore`), so papers must rely on:
  - frozen “task snapshots” under `tasks/`
  - committed configs/scripts + deterministic regeneration steps

