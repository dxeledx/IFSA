#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
REMOTE_ROOT="$(
  awk -F'=' '/rl_root/ {gsub(/"/, "", $2); gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2; exit}' \
    "$REPO_ROOT/codex.remote.toml"
)"

echo "[rl_setup] host:   ${HOST}"
echo "[rl_setup] remote: ${REMOTE_ROOT}"

ssh -o BatchMode=yes "${HOST}" "set -euo pipefail
  cd '${REMOTE_ROOT}'
  if [[ ! -f .venv/bin/activate ]]; then
    rm -rf .venv
    if ! python3 -m venv .venv; then
      echo '[rl_setup] python3 -m venv failed; falling back to virtualenv (no sudo needed).'
      python3 -m pip install --user -U pip virtualenv
      python3 -m virtualenv .venv
    fi
  fi
  . .venv/bin/activate
  pip install -U pip
  pip install -r requirements.txt -r requirements-dev.txt
  pip install -e .
  python -c 'import eapp; print(\"eapp import OK\")'
"

echo "[rl_setup] done"
