#!/usr/bin/env bash
set -euo pipefail

HOST="RLserver-ex"
BEST_TRANS=""
BEST_ONLINE=""

if [[ $# -eq 2 ]]; then
  BEST_TRANS="$1"
  BEST_ONLINE="$2"
elif [[ $# -ge 3 ]]; then
  HOST="$1"
  BEST_TRANS="$2"
  BEST_ONLINE="$3"
else
  echo "Usage: $0 <best_trans_experiment> <best_online_experiment>" >&2
  echo "   or: $0 <host> <best_trans_experiment> <best_online_experiment>" >&2
  echo "Example: $0 RLserver-ex ifsa_v17_desired_shrink0p10 ifsa_v11_2b_online" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

exps=(
  "${BEST_TRANS}"
  "${BEST_ONLINE}"
)

datasets=(bci_iv_2a bci_iv_2b)
tdus=(transductive_unlabeled_all online_prefix_unlabeled)

for exp in "${exps[@]}"; do
  for ds in "${datasets[@]}"; do
    for tdu in "${tdus[@]}"; do
      tau="0.0"
      if [[ "${tdu}" == "online_prefix_unlabeled" ]]; then
        tau="0.5"
      fi

      "${RUN_TMUX}" "${HOST}" "ifsa_final__${exp}__${ds}__${tdu}" \
        "python -m eapp.run experiment=${exp} dataset=${ds} protocol.target_data_usage=${tdu} method.trigger_tau=${tau} runtime.n_jobs=1"
    done
  done
done

