#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

ENV_PREFIX="OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0"

variants=(
  ifsa_v28_ctrl
  ifsa_v28_disc_hold_tau0p01
  ifsa_v28_disc_hold_tau0p012
  ifsa_v28_disc_hold_tau0p02
)

for v in "${variants[@]}"; do
  "${RUN_TMUX}" "${HOST}" "ifsa_roundR__${v}__2a__trans" \
    "${ENV_PREFIX} python -m eapp.run experiment=${v} dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all method.trigger_tau=0.0 runtime.n_jobs=1"
  "${RUN_TMUX}" "${HOST}" "ifsa_roundR__${v}__2b__trans" \
    "${ENV_PREFIX} python -m eapp.run experiment=${v} dataset=bci_iv_2b protocol.target_data_usage=transductive_unlabeled_all method.trigger_tau=0.0 runtime.n_jobs=1"
done
