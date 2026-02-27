#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"
BEST_TRANS="${2:-}"
BEST_ONLINE="${3:-}"

if [[ -z "${BEST_TRANS}" || -z "${BEST_ONLINE}" ]]; then
  echo "Usage: $0 <host> <best_trans_variant> <best_online_variant>" >&2
  echo "Example: $0 RLserver-ex ifsa_v18_safety_hold_q0p95 ifsa_v11_logmean_shrink0p1" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

variants=("${BEST_TRANS}" "${BEST_ONLINE}")
datasets=(bci_iv_2a bci_iv_2b)
tdus=(transductive_unlabeled_all online_prefix_unlabeled)

for v in "${variants[@]}"; do
  for ds in "${datasets[@]}"; do
    for tdu in "${tdus[@]}"; do
      tau="0.0"
      if [[ "${tdu}" == "online_prefix_unlabeled" ]]; then
        tau="0.5"
      fi
      "${RUN_TMUX}" "${HOST}" "ifsa_final_v18__${v}__${ds}__${tdu}" \
        "python -m eapp.run experiment=${v} dataset=${ds} protocol.target_data_usage=${tdu} method.trigger_tau=${tau} runtime.n_jobs=1"
    done
  done
done

