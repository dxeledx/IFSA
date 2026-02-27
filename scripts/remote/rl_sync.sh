#!/usr/bin/env bash
set -euo pipefail

HOST="RLserver-ex"
STRICT_DELETE_EXCLUDED=0

for arg in "$@"; do
  case "$arg" in
    --delete-excluded | --strict-delete-excluded)
      STRICT_DELETE_EXCLUDED=1
      ;;
    *)
      HOST="$arg"
      ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
REMOTE_ROOT="$(
  awk -F'=' '/rl_root/ {gsub(/"/, "", $2); gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2; exit}' \
    "$REPO_ROOT/codex.remote.toml"
)"

if [[ -z "${REMOTE_ROOT}" ]]; then
  echo "Failed to read remote.rl_root from codex.remote.toml" >&2
  exit 1
fi

echo "[rl_sync] repo:   ${REPO_ROOT}"
echo "[rl_sync] host:   ${HOST}"
echo "[rl_sync] remote: ${REMOTE_ROOT}"

SSH_BASE_ARGS=(
  -o BatchMode=yes
  -o ConnectTimeout=10
  -o ServerAliveInterval=30
  -o ServerAliveCountMax=3
)

ssh "${SSH_BASE_ARGS[@]}" "${HOST}" "mkdir -p '${REMOTE_ROOT}'"

RSYNC_BIN="${RSYNC_BIN:-rsync}"
RSYNC_VERSION="$("${RSYNC_BIN}" --version | head -n 1 || true)"

if [[ "${STRICT_DELETE_EXCLUDED}" -eq 1 && "${RSYNC_VERSION}" == openrsync* ]]; then
  echo "[rl_sync] openrsync detected; --delete-excluded would delete remote .venv/data/runs/results."
  echo "[rl_sync] Falling back to safe mode (no --delete-excluded)."
  STRICT_DELETE_EXCLUDED=0
fi

RSYNC_ARGS=(
  -az
  -e "ssh ${SSH_BASE_ARGS[*]}"
  --delete
  "--filter=:- .gitignore"
  --exclude=".venv/"
  --exclude=".venv/***"
  --exclude="data/"
  --exclude="data/***"
  --exclude="runs/"
  --exclude="runs/***"
  --exclude="results/"
  --exclude="results/***"
  --max-size=100m
)

if [[ "${STRICT_DELETE_EXCLUDED}" -eq 1 ]]; then
  RSYNC_ARGS+=(
    --delete-excluded
    "--filter=P .venv/"
    "--filter=P data/"
    "--filter=P runs/"
    "--filter=P results/"
  )
  echo "[rl_sync] mode: strict (delete-excluded + protect)"
else
  echo "[rl_sync] mode: safe (no delete-excluded)"
fi

"${RSYNC_BIN}" "${RSYNC_ARGS[@]}" "${REPO_ROOT}/" "${HOST}:${REMOTE_ROOT}/"

echo "[rl_sync] done"
