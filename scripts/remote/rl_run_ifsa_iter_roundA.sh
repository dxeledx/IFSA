#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

EXPS=(
  ifsa_v12_ctrl
  ifsa_v12_trace_norm
  ifsa_v12_trace_norm_sh0p1
  ifsa_v12_trace_norm_sh0p2
  ifsa_v12_trace_norm_logmean_sh0p1
  ifsa_v12_trace_norm_logmean_sh0p1_idout
)

echo "[rl_run_ifsa_iter_roundA] host: ${HOST}"
echo "[rl_run_ifsa_iter_roundA] starting 12 tmux sessions (6 variants x 2 settings)"

for exp in "${EXPS[@]}"; do
  # A1: bci_iv_2a + transductive (main target)
  dataset="bci_iv_2a"
  tdu="transductive_unlabeled_all"
  label="ifsa_roundA__${exp}__${dataset}__${tdu}"
  cmd="python -m eapp.run experiment=${exp} dataset=${dataset} protocol.target_data_usage=${tdu} method.trigger_tau=0.0 runtime.n_jobs=1"
  "${RUN_TMUX}" "${HOST}" "${label}" "${cmd}"

  # A2: bci_iv_2b + online_prefix (sentinel)
  dataset="bci_iv_2b"
  tdu="online_prefix_unlabeled"
  label="ifsa_roundA__${exp}__${dataset}__${tdu}"
  cmd="python -m eapp.run experiment=${exp} dataset=${dataset} protocol.target_data_usage=${tdu} method.trigger_tau=0.5 runtime.n_jobs=1"
  "${RUN_TMUX}" "${HOST}" "${label}" "${cmd}"
done

echo "[rl_run_ifsa_iter_roundA] done"
echo "[rl_run_ifsa_iter_roundA] tip: ssh -o ConnectTimeout=10 ${HOST} \"tmux ls | grep -c codex-eapp-ifsa_roundA || true\""

