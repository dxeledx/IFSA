#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

ENV_PREFIX="OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0"

# PhysioNet MI (MOABB): transductive_unlabeled_all only (large-scale robustness).
ds="physionet_mi"
tdu="transductive_unlabeled_all"

# Baselines (CSP+LDA pipeline).
baselines=(identity ea ra coral)
for m in "${baselines[@]}"; do
  bash "${RUN_TMUX}" "${HOST}" "physionet_final_v1__${m}__trans" \
    "${ENV_PREFIX} python -m eapp.run dataset=${ds} protocol.target_data_usage=${tdu} method=${m} model=csp_lda runtime.n_jobs=1"
done

# Final IFSA (unified).
bash "${RUN_TMUX}" "${HOST}" "physionet_final_v1__ifsa_final_v1__trans" \
  "${ENV_PREFIX} python -m eapp.run experiment=ifsa_final_v1 dataset=${ds} protocol.target_data_usage=${tdu} method.trigger_tau=0.0 runtime.n_jobs=1"

