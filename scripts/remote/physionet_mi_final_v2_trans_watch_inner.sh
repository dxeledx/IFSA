#!/usr/bin/env bash
set -euo pipefail

# Watch PhysioNetMI final v2 trans runs until completion, then generate reports.

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export PYTHONHASHSEED=0

expected=(
  results/tables/physionet_mi__identity__csp_lda__transductive_unlabeled_all.csv
  results/tables/physionet_mi__ea__csp_lda__transductive_unlabeled_all.csv
  results/tables/physionet_mi__ra__csp_lda__transductive_unlabeled_all.csv
  results/tables/physionet_mi__ra_riemann__csp_lda__transductive_unlabeled_all.csv
  results/tables/physionet_mi__coral__csp_lda__transductive_unlabeled_all.csv
  results/tables/physionet_mi__ifsa_final_v2__csp_lda__transductive_unlabeled_all.csv
  results/tables/physionet_mi__ifsa_final_v2_no_hold__csp_lda__transductive_unlabeled_all.csv
  results/tables/physionet_mi__tsa__tangent_lda__transductive_unlabeled_all.csv
  results/tables/physionet_mi__tsa_ss__tangent_lda__transductive_unlabeled_all.csv
)

while true; do
  missing=0
  for f in "${expected[@]}"; do
    if [[ ! -f "${f}" ]]; then
      missing=$((missing + 1))
    fi
  done

  if [[ "${missing}" -eq 0 ]]; then
    echo "[watch] all runs done at $(date)"
    break
  fi

  running="$(pgrep -af 'python -m eapp.run dataset=physionet_mi' || true)"
  if [[ -z "${running}" ]]; then
    if grep -q 'Traceback' runs/physionet_mi_final_v2_trans.log 2>/dev/null; then
      echo "[watch] runs stopped with error; see runs/physionet_mi_final_v2_trans.log"
      exit 1
    fi
  fi

  echo "[watch] missing=${missing} at $(date)"
  if [[ -n "${running}" ]]; then
    echo "[watch] running: ${running}"
  fi
  sleep 300
done

echo "[watch] generating reports..."
bash scripts/remote/physionet_mi_final_v2_trans_report_inner.sh

echo "[done] watch complete"
