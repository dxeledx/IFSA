#!/usr/bin/env bash
set -euo pipefail

HOST="RLserver-ex"
LABEL=""
CMD=""

if [[ $# -eq 2 ]]; then
  LABEL="$1"
  CMD="$2"
elif [[ $# -ge 3 ]]; then
  HOST="$1"
  LABEL="$2"
  shift 2
  CMD="$*"
else
  echo "Usage: $0 <label> <command>" >&2
  echo "   or: $0 <host> <label> <command...>" >&2
  echo "Example: $0 smoke \"python -m eapp.run experiment=smoke\"" >&2
  echo "Example: $0 RLserver-ex smoke python -m eapp.run experiment=smoke" >&2
  exit 2
fi

SAFE_LABEL="$(echo "${LABEL}" | tr -cs 'a-zA-Z0-9._-' '_' | sed 's/^_*//;s/_*$//')"
TS="$(date +%Y%m%d-%H%M%S)"
SESSION="codex-eapp-${SAFE_LABEL}-${TS}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
REMOTE_ROOT="$(
  awk -F'=' '/rl_root/ {gsub(/"/, "", $2); gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2; exit}' \
    "$REPO_ROOT/codex.remote.toml"
)"

LOG_PATH="runs/${SAFE_LABEL}.log"

echo "[rl_run_tmux] host:    ${HOST}"
echo "[rl_run_tmux] session: ${SESSION}"
echo "[rl_run_tmux] log:     ${LOG_PATH}"
echo "[rl_run_tmux] cmd:     ${CMD}"

SSH_BASE_ARGS=(
  -o BatchMode=yes
  -o ConnectTimeout=10
  -o ServerAliveInterval=30
  -o ServerAliveCountMax=3
)

ssh "${SSH_BASE_ARGS[@]}" "${HOST}" "set -euo pipefail
  cd '${REMOTE_ROOT}'
  mkdir -p runs
  # Use -c to avoid relying on tmux server's default-path.
  # Avoid '&&' before the pipe so logs are created even if activation fails.
  tmux new -d -s '${SESSION}' -c '${REMOTE_ROOT}' \\
    \"bash -lc 'set -euo pipefail; { . .venv/bin/activate; ${CMD}; } 2>&1 | tee -a ${LOG_PATH}'\"
  echo 'tmux session started: ${SESSION}'
"

echo "[rl_run_tmux] attach: ssh -t ${HOST} \"tmux attach -t ${SESSION}\""
echo "[rl_run_tmux] tail:   ssh -o BatchMode=yes ${HOST} \"cd '${REMOTE_ROOT}' && tail -n 200 ${LOG_PATH}\""
