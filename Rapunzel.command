#!/bin/bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
LOG_FILE="$REPO_DIR/rapunzel-launch.log"

{
  echo
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') Rapunzel.command ====="
} >> "$LOG_FILE"
exec >> "$LOG_FILE" 2>&1

PYTHON_BIN=""
if [ -x "$REPO_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$REPO_DIR/.venv/bin/python"
elif [ -x /opt/homebrew/bin/python3 ]; then
  PYTHON_BIN=/opt/homebrew/bin/python3
elif [ -x /usr/local/bin/python3 ]; then
  PYTHON_BIN=/usr/local/bin/python3
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "python3 is required but was not found on PATH."
  echo "Run ./install.sh after installing Python 3."
  exit 1
fi

cd "$REPO_DIR"
echo "repo=$REPO_DIR"
echo "python=$PYTHON_BIN"

if [ ! -f "$REPO_DIR/webui/dist/app.js" ]; then
  echo "Missing built frontend: $REPO_DIR/webui/dist/app.js"
  echo "Run ./install.sh first."
  exit 1
fi

exec "$PYTHON_BIN" "$REPO_DIR/app.py"
