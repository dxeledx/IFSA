#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

DATASETS=(bci_iv_2a bci_iv_2b)
TDUS=(transductive_unlabeled_all online_prefix_unlabeled)
METHODS=(identity ea ra ra_riemann coral)

echo "[rl_run_alignment_baselines_csp_lda_v2] host: ${HOST}"
echo "[rl_run_alignment_baselines_csp_lda_v2] starting 20 tmux sessions (2 datasets x 2 protocols x 5 methods)"

for dataset in "${DATASETS[@]}"; do
  for tdu in "${TDUS[@]}"; do
    for method in "${METHODS[@]}"; do
      label="baseline_align_v2__${dataset}__${tdu}__csp_lda__${method}"
      cmd="python -m eapp.run dataset=${dataset} protocol.target_data_usage=${tdu} model=csp_lda method=${method} runtime.n_jobs=1"
      "${RUN_TMUX}" "${HOST}" "${label}" "${cmd}"
    done
  done
done

echo "[rl_run_alignment_baselines_csp_lda_v2] done"
echo "[rl_run_alignment_baselines_csp_lda_v2] tip: ssh -o BatchMode=yes ${HOST} \"tmux ls | head\""

