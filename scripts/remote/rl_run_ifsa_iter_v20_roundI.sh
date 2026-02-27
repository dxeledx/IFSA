#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

variants=(
  ifsa_v20_ctrl
  ifsa_v20_disc_hold_tau0p05
  ifsa_v20_disc_hold_tau0p10
  ifsa_v20_disc_hold_tau0p15
)

for v in "${variants[@]}"; do
  "${RUN_TMUX}" "${HOST}" "ifsa_roundI__${v}__2a__trans" \
    "python -m eapp.run experiment=${v} dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all method.trigger_tau=0.0 runtime.n_jobs=1"
  "${RUN_TMUX}" "${HOST}" "ifsa_roundI__${v}__2b__online" \
    "python -m eapp.run experiment=${v} dataset=bci_iv_2b protocol.target_data_usage=online_prefix_unlabeled method.trigger_tau=0.5 runtime.n_jobs=1"
done

