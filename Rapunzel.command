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
if [ -x /opt/homebrew/bin/python3 ]; then
  PYTHON_BIN=/opt/homebrew/bin/python3
elif [ -x /usr/local/bin/python3 ]; then
  PYTHON_BIN=/usr/local/bin/python3
else
  PYTHON_BIN="$(command -v python3)"
fi

cd "$REPO_DIR"
echo "repo=$REPO_DIR"
echo "python=$PYTHON_BIN"
exec "$PYTHON_BIN" "$REPO_DIR/app.py"
