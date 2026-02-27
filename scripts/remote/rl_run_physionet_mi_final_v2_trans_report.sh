#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

bash "${RUN_TMUX}" "${HOST}" "physionet_mi_final_v2_trans_report" \
  "bash scripts/remote/physionet_mi_final_v2_trans_report_inner.sh"

