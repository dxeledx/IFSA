#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

ENV_PREFIX="OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0"

# Best transductive candidate (v23) + best online candidate (v11), but only run
# the settings that were not covered in the gate rounds.
tasks=(
  "ifsa_v23_track_scale_tau0p5_hold0p5_disc0p001 bci_iv_2a online_prefix_unlabeled 0.5"
  "ifsa_v23_track_scale_tau0p5_hold0p5_disc0p001 bci_iv_2b transductive_unlabeled_all 0.0"
  "ifsa_v11_logmean_shrink0p1_generic bci_iv_2a transductive_unlabeled_all 0.0"
  "ifsa_v11_logmean_shrink0p1_generic bci_iv_2a online_prefix_unlabeled 0.5"
  "ifsa_v11_logmean_shrink0p1_generic bci_iv_2b transductive_unlabeled_all 0.0"
)

for t in "${tasks[@]}"; do
  read -r v ds tdu tau <<<"${t}"
  "${RUN_TMUX}" "${HOST}" "ifsa_final_v23_missing__${v}__${ds}__${tdu}" \
    "${ENV_PREFIX} python -m eapp.run experiment=${v} dataset=${ds} protocol.target_data_usage=${tdu} method.trigger_tau=${tau} runtime.n_jobs=1"
done

