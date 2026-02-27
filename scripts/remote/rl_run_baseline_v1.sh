#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

DATASETS=(bci_iv_2a bci_iv_2b)
TDUS=(transductive_unlabeled_all online_prefix_unlabeled)

echo "[rl_run_baseline_v1] host: ${HOST}"
echo "[rl_run_baseline_v1] starting 36 tmux sessions (2 datasets x 2 protocols x (4+5) methods)"

for dataset in "${DATASETS[@]}"; do
  for tdu in "${TDUS[@]}"; do
    # ---- csp_lda ----
    for method in identity ea ra coral; do
      label="baseline_v1__${dataset}__${tdu}__csp_lda__${method}"
      cmd="python -m eapp.run dataset=${dataset} protocol.target_data_usage=${tdu} model=csp_lda method=${method}"
      "${RUN_TMUX}" "${HOST}" "${label}" "${cmd}"
    done

    # ---- mdm ----
    for method in identity ea ra coral tl_center_scale; do
      label="baseline_v1__${dataset}__${tdu}__mdm__${method}"
      cmd="python -m eapp.run dataset=${dataset} protocol.target_data_usage=${tdu} model=mdm method=${method}"
      "${RUN_TMUX}" "${HOST}" "${label}" "${cmd}"
    done
  done
done

echo "[rl_run_baseline_v1] done"
echo "[rl_run_baseline_v1] tip: ssh -o BatchMode=yes ${HOST} \"tmux ls | head\""

