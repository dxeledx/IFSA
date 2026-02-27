#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
RUN_TMUX="${REPO_ROOT}/scripts/remote/rl_run_tmux.sh"

ENV_PREFIX="OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0"

variant_ifsa="ifsa_final_v1"
variant_tsa="tsa"
variant_tsa_ss="tsa_ss"

settings=(
  "bci_iv_2a transductive_unlabeled_all 0.0"
  "bci_iv_2b transductive_unlabeled_all 0.0"
  "bci_iv_2a online_prefix_unlabeled 0.5"
  "bci_iv_2b online_prefix_unlabeled 0.5"
)

for spec in "${settings[@]}"; do
  read -r ds tdu tau <<<"${spec}"

  label_tdu="trans"
  if [[ "${tdu}" != "transductive_unlabeled_all" ]]; then
    label_tdu="online"
  fi

  # IFSA-final v1 (CSP+LDA)
  bash "${RUN_TMUX}" "${HOST}" "unify__${variant_ifsa}__${ds}__${label_tdu}" \
    "${ENV_PREFIX} python -m eapp.run experiment=${variant_ifsa} dataset=${ds} protocol.target_data_usage=${tdu} method.trigger_tau=${tau} runtime.n_jobs=1"

  # TSA (tangent_lda)
  bash "${RUN_TMUX}" "${HOST}" "unify__${variant_tsa}__${ds}__${label_tdu}" \
    "${ENV_PREFIX} python -m eapp.run experiment=${variant_tsa} dataset=${ds} protocol.target_data_usage=${tdu} runtime.n_jobs=1"

  # TSA-SS (tangent_lda)
  bash "${RUN_TMUX}" "${HOST}" "unify__${variant_tsa_ss}__${ds}__${label_tdu}" \
    "${ENV_PREFIX} python -m eapp.run experiment=${variant_tsa_ss} dataset=${ds} protocol.target_data_usage=${tdu} runtime.n_jobs=1"
done

# Determinism seedcheck (only 2a/trans for IFSA-final v1).
bash "${RUN_TMUX}" "${HOST}" "unify_seedcheck__${variant_ifsa}__bci_iv_2a__trans" \
  "${ENV_PREFIX} python -m eapp.run experiment=${variant_ifsa} dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all method.trigger_tau=0.0 runtime.n_jobs=1 runtime.seed=43 runtime.results_dir=results_seedcheck_final_v1"

