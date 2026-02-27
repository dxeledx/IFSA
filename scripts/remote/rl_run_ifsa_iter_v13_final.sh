#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

# v13 final candidates (selected from Round-C gate):
# - best_trans: ifsa_v13_tg_beta1_full
# - best_online: ifsa_v11_logmean_shrink0p1 (defined by experiment=ifsa_v11_2b_online)
exps=(
  ifsa_v13_tg_beta1_full
  ifsa_v11_2b_online
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

