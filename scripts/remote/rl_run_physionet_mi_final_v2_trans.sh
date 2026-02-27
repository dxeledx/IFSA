#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

# Run as a single tmux session to avoid OOM (PhysioNetMI loads full dataset).
bash "${RUN_TMUX}" "${HOST}" "physionet_mi_final_v2_trans" \
  "bash scripts/remote/physionet_mi_final_v2_trans_inner.sh"

