#!/usr/bin/env bash
set -euo pipefail

# PhysioNet MI (MOABB) - post-run reporting for final v2 transductive experiment.

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export PYTHONHASHSEED=0

ds="physionet_mi"
tdu="transductive_unlabeled_all"

python -m eapp.report dataset="${ds}" protocol.target_data_usage="${tdu}"

python -m eapp.report_matrix \
  --models csp_lda,tangent_lda \
  --datasets "${ds}" \
  --target-data-usages "${tdu}" \
  --methods identity,ea,ra,ra_riemann,coral,ifsa,tsa,tsa_ss

python -m eapp.report_pairwise \
  --dataset "${ds}" \
  --target-data-usage "${tdu}" \
  --model csp_lda \
  --target-variant ifsa_final_v2 \
  --baselines ea,ra,ra_riemann,coral,identity \
  --no-plot

python -m eapp.report_pairwise \
  --dataset "${ds}" \
  --target-data-usage "${tdu}" \
  --model tangent_lda \
  --target-variant tsa_ss \
  --baselines tsa \
  --no-plot

echo "[done] physionet_mi final v2 trans reports complete"

