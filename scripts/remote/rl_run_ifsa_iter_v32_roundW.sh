#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

ENV_PREFIX="OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0"

variant="ifsa_v32_euclid_thrust_track_scale_tau0p5_hold0p5_disc0p001"

bash "${RUN_TMUX}" "${HOST}" "ifsa_roundW__${variant}__2a__trans" \
  "${ENV_PREFIX} python -m eapp.run experiment=${variant} dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all method.trigger_tau=0.0 runtime.n_jobs=1"

bash "${RUN_TMUX}" "${HOST}" "ifsa_roundW__${variant}__2b__trans" \
  "${ENV_PREFIX} python -m eapp.run experiment=${variant} dataset=bci_iv_2b protocol.target_data_usage=transductive_unlabeled_all method.trigger_tau=0.0 runtime.n_jobs=1"

# Determinism check (repeat 2a/trans with a different seed into a separate results dir).
bash "${RUN_TMUX}" "${HOST}" "ifsa_roundW__${variant}__2a__trans_seed43" \
  "${ENV_PREFIX} python -m eapp.run experiment=${variant} dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all method.trigger_tau=0.0 runtime.n_jobs=1 runtime.seed=43 runtime.results_dir=results_seedcheck_v32"
