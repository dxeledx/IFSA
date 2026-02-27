# Baseline Suite v1 (frozen)

Date: **2026-02-26**  
Code snapshot: `428a9f2f0ec6b0b23321ca301c21b7288a3eb653d5ea79337f48dd4cb89cd5be` (see `env.json`)

This folder is a frozen baseline snapshot for future comparisons. It covers:

- **Datasets**: `bci_iv_2a` (4-class MI), `bci_iv_2b` (2-class MI)
- **Protocols**: `transductive_unlabeled_all`, `online_prefix_unlabeled` (prefix size from `configs/protocol/loso.yaml`)
- **Models**: `csp_lda`, `mdm`
- **No target labels are used** (only unlabeled target trials are used for alignment when the protocol allows).

## Methods (fixed)

### `csp_lda`
- `identity`
- `ea` (Euclidean Alignment)
- `ra` (log-Euclidean re-centering)
- `coral` (CORAL: align source to target covariance mean)

### `mdm`
- `identity`
- `ea`
- `ra`
- `coral` (note: with affine-invariant MDM metric, `coral` is effectively equivalent to `ra`)
- `tl_center_scale` (pyRiemann: `TLCenter + TLScale`, no rotation / no target labels)

## Files in this snapshot

- Matrices (method × setting):
  - `matrix__csp_lda__acc_mean.csv`, `matrix__csp_lda__neg_transfer_ratio.csv`, `matrix__csp_lda__best_variant.csv`
  - `matrix__mdm__acc_mean.csv`, `matrix__mdm__neg_transfer_ratio.csv`, `matrix__mdm__best_variant.csv`
  - Note: matrices are filtered to the **Baseline Suite v1** methods only.
- Per-setting summaries (used to generate matrices):
  - `summary__bci_iv_2a__transductive_unlabeled_all.csv`
  - `summary__bci_iv_2a__online_prefix_unlabeled.csv`
  - `summary__bci_iv_2b__transductive_unlabeled_all.csv`
  - `summary__bci_iv_2b__online_prefix_unlabeled.csv`
- Run metadata:
  - `env.json` (includes `pip_freeze`, `code_manifest`, `code_snapshot_sha256`)
  - `config.yaml` (one example resolved config from a baseline run)

## How to reproduce (RLserver-ex)

From repo root on your local machine:

```bash
./scripts/remote/rl_sync.sh RLserver-ex
./scripts/remote/rl_setup.sh RLserver-ex
./scripts/remote/rl_run_baseline_v1.sh RLserver-ex

# wait until tmux sessions finish:
ssh -o BatchMode=yes RLserver-ex "tmux ls | grep -c codex-eapp-baseline_v1 || true"

./scripts/remote/rl_fetch_results.sh RLserver-ex

# regenerate summaries + matrices locally:
./.venv/bin/python -m eapp.report dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all
./.venv/bin/python -m eapp.report dataset=bci_iv_2a protocol.target_data_usage=online_prefix_unlabeled
./.venv/bin/python -m eapp.report dataset=bci_iv_2b protocol.target_data_usage=transductive_unlabeled_all
./.venv/bin/python -m eapp.report dataset=bci_iv_2b protocol.target_data_usage=online_prefix_unlabeled

./.venv/bin/python -m eapp.report_matrix \
  --models csp_lda,mdm \
  --datasets bci_iv_2a,bci_iv_2b \
  --target-data-usages transductive_unlabeled_all,online_prefix_unlabeled
```

## References (starting point)

- He, H. & Wu, D. “Transfer Learning for Brain-Computer Interfaces: A Euclidean Space Data Alignment Approach.” (EA)
- Zanini, P. et al. “Transfer Learning: A Riemannian Geometry Framework With Applications to Brain–Computer Interfaces.” (TLCenter)
- Rodrigues, P. L. C. et al. “Riemannian Procrustes analysis: transfer learning for brain-computer interfaces.” (TLScale / RPA family)
- Sun, B. & Saenko, K. “Deep CORAL: Correlation Alignment for Deep Domain Adaptation.” (CORAL)
