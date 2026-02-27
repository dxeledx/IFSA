#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

# 2-setting gate:
# - bci_iv_2a / transductive_unlabeled_all (main target)
# - bci_iv_2b / online_prefix_unlabeled (sentinel: no regression)
exp_methods=(
  ifsa_v14_tg_beta1_full_lw
  ra_v14_lw
  coral_v14_lw
)

for exp in "${exp_methods[@]}"; do
  "${RUN_TMUX}" "${HOST}" "v14_lw__${exp}__2a__trans" \
    "python -m eapp.run experiment=${exp} dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all runtime.n_jobs=1"

  if [[ "${exp}" == ifsa_* ]]; then
    "${RUN_TMUX}" "${HOST}" "v14_lw__${exp}__2b__online" \
      "python -m eapp.run experiment=${exp} dataset=bci_iv_2b protocol.target_data_usage=online_prefix_unlabeled method.trigger_tau=0.5 runtime.n_jobs=1"
  else
    "${RUN_TMUX}" "${HOST}" "v14_lw__${exp}__2b__online" \
      "python -m eapp.run experiment=${exp} dataset=bci_iv_2b protocol.target_data_usage=online_prefix_unlabeled runtime.n_jobs=1"
  fi
done
