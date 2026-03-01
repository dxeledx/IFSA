# Testing

## Test Framework
- Test runner: `pytest`
- Lint: `ruff`
- Quick syntax check: `python -m compileall -q src`

## Commands
```bash
python3 -m compileall -q src
.venv/bin/ruff check .
.venv/bin/pytest -q tests
```

## What’s Covered
Unit tests focus on “math + contracts + leakage prevention”:
- SPD utility correctness: `tests/test_spd.py`
- IFSA core behavior:
  - `tests/test_ifsa.py`
  - `tests/test_ifsa_euclid_thrust.py`
  - `tests/test_ifsa_split_half_score.py`
  - `tests/test_ifsa_disc_loss_score.py`
  - `tests/test_ifsa_low_score_hold_rule.py`
- CORAL / RA-Riemann basic correctness:
  - `tests/test_coral.py`
  - `tests/test_ra_riemann.py`
- Protocol leakage checks (target label usage constraints):
  - `tests/test_protocol_leakage.py`
- Statistical routines (Holm/Wilcoxon robustness):
  - `tests/test_stats_multi.py`

## Integration Tests / Smoke
There are lightweight “does it run” tests for pipeline glue:
- `tests/test_tl_center_scale_smoke.py`
- `tests/test_tsa_guard.py`

## Determinism Checks
For experiments, determinism is validated via:
- fixed BLAS thread env vars
- explicit `runtime.seed`
- CSV diff scripts (e.g. `scripts/analysis/check_seed_determinism_csv.py`)

