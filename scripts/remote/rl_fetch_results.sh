#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-RLserver-ex}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
REMOTE_ROOT="$(
  awk -F'=' '/rl_root/ {gsub(/"/, "", $2); gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2; exit}' \
    "$REPO_ROOT/codex.remote.toml"
)"

echo "[rl_fetch_results] host:   ${HOST}"
echo "[rl_fetch_results] remote: ${REMOTE_ROOT}"

mkdir -p "${REPO_ROOT}/results/tables" "${REPO_ROOT}/results/figures" "${REPO_ROOT}/runs/remote_logs"

SSH_BASE_ARGS=(
  -o BatchMode=yes
  -o ConnectTimeout=10
  -o ServerAliveInterval=30
  -o ServerAliveCountMax=3
)
RSYNC_SSH="ssh ${SSH_BASE_ARGS[*]}"

rsync -az -e "${RSYNC_SSH}" "${HOST}:${REMOTE_ROOT}/results/tables/" "${REPO_ROOT}/results/tables/" || true
rsync -az -e "${RSYNC_SSH}" "${HOST}:${REMOTE_ROOT}/results/figures/" "${REPO_ROOT}/results/figures/" || true

rsync -az --include='*/' --include='*.log' --exclude='*' \
  -e "${RSYNC_SSH}" "${HOST}:${REMOTE_ROOT}/runs/" "${REPO_ROOT}/runs/remote_logs/" || true

rsync -az --include='*/' --include='config.yaml' --include='env.json' --exclude='*' \
  -e "${RSYNC_SSH}" "${HOST}:${REMOTE_ROOT}/runs/" "${REPO_ROOT}/runs/remote_logs/" || true

echo "[rl_fetch_results] done"
