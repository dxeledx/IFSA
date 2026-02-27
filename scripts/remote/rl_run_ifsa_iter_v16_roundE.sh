#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

variants=(
  ifsa_v16_tg_beta1_full_disp0p5
  ifsa_v16_tg_beta1_full_disp1p0
)

for v in "${variants[@]}"; do
  "${RUN_TMUX}" "${HOST}" "ifsa_roundE__${v}__2a__trans" \
    "python -m eapp.run experiment=${v} dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all method.trigger_tau=0.0 runtime.n_jobs=1"
  "${RUN_TMUX}" "${HOST}" "ifsa_roundE__${v}__2b__online" \
    "python -m eapp.run experiment=${v} dataset=bci_iv_2b protocol.target_data_usage=online_prefix_unlabeled method.trigger_tau=0.5 runtime.n_jobs=1"
done

