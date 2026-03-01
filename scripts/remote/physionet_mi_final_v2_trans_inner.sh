#!/usr/bin/env bash
set -euo pipefail

# PhysioNet MI (MOABB) - transductive_unlabeled_all only.
# Runs sequentially to avoid loading the full dataset into memory multiple times.

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export PYTHONHASHSEED=0
export PYTHONUNBUFFERED=1

# Parallelize covariance computation (safe) while keeping LOSO folds sequential
# to avoid blowing up memory (each fold slices a near-full copy of x_train).
export EAPP_COV_N_JOBS="${EAPP_COV_N_JOBS:-32}"

ds="physionet_mi"
tdu="transductive_unlabeled_all"
# PhysioNetMI can contain runs with slightly different sampling rates; resample to
# a fixed rate to make MOABB/MNE epoch concatenation deterministic/stable.
resample=160
fold_jobs=1
subj_jobs=1

# CSP + LDA baselines (same pipeline).
python -m eapp.run dataset="${ds}" protocol.target_data_usage="${tdu}" \
  preprocess.resample="${resample}" method=identity model=csp_lda runtime.n_jobs="${fold_jobs}" \
  eval.subject_n_jobs="${subj_jobs}" eval.trim_memory=true eval.compute_baseline=false

python -m eapp.run dataset="${ds}" protocol.target_data_usage="${tdu}" \
  preprocess.resample="${resample}" method=ea model=csp_lda runtime.n_jobs="${fold_jobs}" \
  eval.subject_n_jobs="${subj_jobs}" eval.trim_memory=true eval.compute_baseline=false

python -m eapp.run dataset="${ds}" protocol.target_data_usage="${tdu}" \
  preprocess.resample="${resample}" method=ra model=csp_lda runtime.n_jobs="${fold_jobs}" \
  eval.subject_n_jobs="${subj_jobs}" eval.trim_memory=true eval.compute_baseline=false

python -m eapp.run dataset="${ds}" protocol.target_data_usage="${tdu}" \
  preprocess.resample="${resample}" method=ra_riemann model=csp_lda runtime.n_jobs="${fold_jobs}" \
  eval.subject_n_jobs="${subj_jobs}" eval.trim_memory=true eval.compute_baseline=false

python -m eapp.run dataset="${ds}" protocol.target_data_usage="${tdu}" \
  preprocess.resample="${resample}" method=coral model=csp_lda runtime.n_jobs="${fold_jobs}" \
  eval.subject_n_jobs="${subj_jobs}" eval.trim_memory=true eval.compute_baseline=false

# Unified IFSA (Final v2).
python -m eapp.run experiment=ifsa_final_v2 dataset="${ds}" protocol.target_data_usage="${tdu}" \
  preprocess.resample="${resample}" method.trigger_tau=0.0 runtime.n_jobs="${fold_jobs}" \
  eval.subject_n_jobs="${subj_jobs}" eval.trim_memory=true eval.compute_baseline=false

# IFSA final v2 (no-hold diagnostic).
python -m eapp.run experiment=ifsa_final_v2 experiment_name=ifsa_final_v2_no_hold \
  dataset="${ds}" protocol.target_data_usage="${tdu}" preprocess.resample="${resample}" \
  method.trigger_tau=0.0 runtime.n_jobs="${fold_jobs}" eval.subject_n_jobs="${subj_jobs}" \
  eval.trim_memory=true eval.compute_baseline=false \
  method.safety_hold_gate_threshold=0.0 method.safety_low_score_mult=0.0

# Tangent-LDA baselines (different pipeline; reported in separate table).
python -m eapp.run experiment=tsa dataset="${ds}" protocol.target_data_usage="${tdu}" \
  preprocess.resample="${resample}" runtime.n_jobs="${fold_jobs}" eval.subject_n_jobs="${subj_jobs}" \
  eval.trim_memory=true eval.compute_baseline=false

python -m eapp.run experiment=tsa_ss dataset="${ds}" protocol.target_data_usage="${tdu}" \
  preprocess.resample="${resample}" runtime.n_jobs="${fold_jobs}" eval.subject_n_jobs="${subj_jobs}" \
  eval.trim_memory=true eval.compute_baseline=false

echo "[done] physionet_mi final v2 trans runs complete"

echo "[post] generating reports..."
bash scripts/remote/physionet_mi_final_v2_trans_report_inner.sh

echo "[done] physionet_mi final v2 trans run + report complete"
