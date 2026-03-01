# Conventions

## Python Style
- Type hints everywhere; `from __future__ import annotations` is used consistently.
- Dataclasses for configs/metrics (`@dataclass(frozen=True)`).
- Numpy-first numerical code; SPD operations centralized in `src/eapp/utils/spd.py`.
- Linting: `ruff` with 100-char line length (`pyproject.toml`).

## Alignment Method Pattern
Signal aligners generally follow:
- `fit(x: np.ndarray) -> self`
- `transform(x: np.ndarray) -> np.ndarray`

Examples:
- `src/eapp/alignment/ea.py::EASignalAligner`
- `src/eapp/alignment/ifsa.py::IFSASignalAligner`

The aligner exposes:
- `aligner.matrix` (alignment matrix)
- optional `aligner.metrics` (recorded diagnostics; serialized into per-subject CSV)

## SPD Handling Rules
- Always symmetrize when appropriate: `sym(...)`.
- Use stable SPD functions with epsilon:
  - `logm_spd`, `expm_sym`, `sqrtm_spd`, `invsqrtm_spd`
- Keep “reference-covariance source-only” invariant:
  - IFSA inertial reference `R_*` is computed from source data only in
    `src/eapp/eval/loso.py::_ifsa_reference_cov()`.

## Hydra Conventions
- Main invocation pattern:
  - `python -m eapp.run experiment=<variant> dataset=<name> protocol.target_data_usage=<tdu> ...`
- Experiment naming:
  - `variant` is taken from `experiment_name` (if provided) or falls back to `method.name`
  - Output tables follow: `{dataset}__{variant}__{model}__{tdu}.csv`

## Remote Experiment Conventions (RLserver)
- Prefer tmux for long runs; sessions created by `rl_run_tmux.sh` are prefixed with `codex-`.
- WAN-safe sync uses `.gitignore`-aware rsync filters; never sync `data/` by default.
- Determinism:
  - Force single-thread BLAS (`OMP/MKL/OPENBLAS/NUMEXPR=1`)
  - Fix hash seed (`PYTHONHASHSEED=0`)

