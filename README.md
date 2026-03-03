# IFSA (Research Infra)

Cross-subject EEG alignment research infra (EA / RA / TSA + IFSA / TSA-SS), CPU-first and
reproducibility-first.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
```

Quick smoke run (downloads data on first run):

```bash
python -m eapp.run experiment=smoke
```

More examples:

```bash
# IFSA
python -m eapp.run experiment=ifsa
python -m eapp.run experiment=ifsa_no_spec
python -m eapp.run experiment=ifsa_no_damp
python -m eapp.run experiment=ifsa_no_energy
python -m eapp.run experiment=ifsa_trigger

# TSA-SS
python -m eapp.run experiment=tsa_ss
```

Outputs:
- `runs/`: hydra run folders (configs/logs)
- `results/tables/`: CSV results
- `results/figures/`: plots

## RLserver-ex (CPU) remote workflow

1) Sync code (WAN-safe; does **not** sync `data/`):

```bash
./scripts/remote/rl_sync.sh

# Optional: strict cleanup on remote (delete excluded files) when using rsync>=3 on local.
# On macOS openrsync, the script will automatically fall back to safe mode.
./scripts/remote/rl_sync.sh RLserver-ex --delete-excluded
```

2) Setup Python venv on remote (one-time):

```bash
./scripts/remote/rl_setup.sh
```

3) Run experiment in tmux (detached):

```bash
./scripts/remote/rl_run_tmux.sh smoke "python -m eapp.run experiment=smoke"

# Or explicitly pass host:
./scripts/remote/rl_run_tmux.sh RLserver-ex smoke python -m eapp.run experiment=smoke
```

4) Fetch back small artifacts (tables/figures/logs):

```bash
./scripts/remote/rl_fetch_results.sh
```

## Paper-friendly summary report

Generate a summary CSV + figure from existing `results/tables/*.csv`:

```bash
python -m eapp.report dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all
python -m eapp.report dataset=bci_iv_2a protocol.target_data_usage=online_prefix_unlabeled
python -m eapp.report dataset=bci_iv_2b protocol.target_data_usage=transductive_unlabeled_all
python -m eapp.report dataset=bci_iv_2b protocol.target_data_usage=online_prefix_unlabeled
```

## Cross-setting result matrix

After generating the per-setting summaries, aggregate them into a single “report matrix”
across datasets + protocols:

```bash
python -m eapp.report_matrix --models csp_lda \
  --datasets bci_iv_2a,bci_iv_2b \
  --target-data-usages transductive_unlabeled_all,online_prefix_unlabeled
```

Outputs (under `results/tables/`):
- `matrix__csp_lda__acc_mean.csv` (methods × settings)
- `matrix__csp_lda__neg_transfer_ratio.csv`
- `matrix__csp_lda__best_variant.csv` (which variant was selected as “best” per method family)

## Notes

- By default datasets are downloaded/cached under `data/` (configurable).
- For strict evaluations, use `protocol.target_data_usage=online_prefix_unlabeled` to avoid
  “peek at future trials” leakage.
