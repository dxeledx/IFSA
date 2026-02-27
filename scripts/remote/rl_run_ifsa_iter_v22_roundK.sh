#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

# Keep the run deterministic (and a bit cheaper) on CPU.
ENV_PREFIX="OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0"

variants=(
  ifsa_v22_track_scale_q0p90_tau0p5_disc0p001
  ifsa_v22_track_scale_q0p90_tau0p7_disc0p001
  ifsa_v22_track_scale_q0p90_tau0p5_disc0p002
  ifsa_v22_track_scale_q0p90_tau0p7_disc0p002
)

for v in "${variants[@]}"; do
  "${RUN_TMUX}" "${HOST}" "ifsa_roundK__${v}__2a__trans" \
    "${ENV_PREFIX} python -m eapp.run experiment=${v} dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all method.trigger_tau=0.0 runtime.n_jobs=1"
  "${RUN_TMUX}" "${HOST}" "ifsa_roundK__${v}__2b__online" \
    "${ENV_PREFIX} python -m eapp.run experiment=${v} dataset=bci_iv_2b protocol.target_data_usage=online_prefix_unlabeled method.trigger_tau=0.5 runtime.n_jobs=1"
done

