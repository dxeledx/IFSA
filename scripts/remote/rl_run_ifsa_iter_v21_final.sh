#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

variants=(
  ifsa_v21_track_hold_q0p90_disc0p001
  ifsa_v11_logmean_shrink0p1_generic
)

datasets=(bci_iv_2a bci_iv_2b)
tdus=(transductive_unlabeled_all online_prefix_unlabeled)

for v in "${variants[@]}"; do
  for ds in "${datasets[@]}"; do
    for tdu in "${tdus[@]}"; do
      tau="0.0"
      if [[ "${tdu}" == "online_prefix_unlabeled" ]]; then
        tau="0.5"
      fi
      "${RUN_TMUX}" "${HOST}" "ifsa_final_v21__${v}__${ds}__${tdu}" \
        "python -m eapp.run experiment=${v} dataset=${ds} protocol.target_data_usage=${tdu} method.trigger_tau=${tau} runtime.n_jobs=1"
    done
  done
done

