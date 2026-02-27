#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

ENV_PREFIX="OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0"

variant="coral_safe_v1"

"${RUN_TMUX}" "${HOST}" "coral_safe_gate__2a__trans" \
  "${ENV_PREFIX} python -m eapp.run experiment=${variant} dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all runtime.n_jobs=1"

"${RUN_TMUX}" "${HOST}" "coral_safe_gate__2b__online" \
  "${ENV_PREFIX} python -m eapp.run experiment=${variant} dataset=bci_iv_2b protocol.target_data_usage=online_prefix_unlabeled runtime.n_jobs=1"

