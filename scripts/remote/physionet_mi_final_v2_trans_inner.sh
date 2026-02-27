#!/usr/bin/env bash
set -euo pipefail

# PhysioNet MI (MOABB) - transductive_unlabeled_all only.
# Runs sequentially to avoid loading the full dataset into memory multiple times.

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export PYTHONHASHSEED=0

ds="physionet_mi"
tdu="transductive_unlabeled_all"

# CSP + LDA baselines (same pipeline).
python -m eapp.run dataset="${ds}" protocol.target_data_usage="${tdu}" \
  method=identity model=csp_lda runtime.n_jobs=8 eval.compute_baseline=false

python -m eapp.run dataset="${ds}" protocol.target_data_usage="${tdu}" \
  method=ea model=csp_lda runtime.n_jobs=8 eval.compute_baseline=false

python -m eapp.run dataset="${ds}" protocol.target_data_usage="${tdu}" \
  method=ra model=csp_lda runtime.n_jobs=8 eval.compute_baseline=false

python -m eapp.run dataset="${ds}" protocol.target_data_usage="${tdu}" \
  method=ra_riemann model=csp_lda runtime.n_jobs=8 eval.compute_baseline=false

python -m eapp.run dataset="${ds}" protocol.target_data_usage="${tdu}" \
  method=coral model=csp_lda runtime.n_jobs=8 eval.compute_baseline=false

# Unified IFSA (Final v2).
python -m eapp.run experiment=ifsa_final_v2 dataset="${ds}" protocol.target_data_usage="${tdu}" \
  method.trigger_tau=0.0 runtime.n_jobs=8 eval.compute_baseline=false

# Tangent-LDA baselines (different pipeline; reported in separate table).
python -m eapp.run experiment=tsa dataset="${ds}" protocol.target_data_usage="${tdu}" \
  runtime.n_jobs=8 eval.compute_baseline=false

python -m eapp.run experiment=tsa_ss dataset="${ds}" protocol.target_data_usage="${tdu}" \
  runtime.n_jobs=8 eval.compute_baseline=false

echo "[done] physionet_mi final v2 trans runs complete"

