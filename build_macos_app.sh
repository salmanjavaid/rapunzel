#!/bin/bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export PYTHONPATH="$REPO_DIR/.deps:$REPO_DIR/.build-deps"
export PYINSTALLER_CONFIG_DIR="$REPO_DIR/.pyinstaller"

cd "$REPO_DIR"
mkdir -p "$PYINSTALLER_CONFIG_DIR"
rm -rf build dist
bash "$REPO_DIR/scripts/generate_app_icon.sh"
python3 -m PyInstaller rapunzel_pyinstaller.spec
codesign --force --deep -s - "dist/Rapunzel.app"
echo "Built: $REPO_DIR/dist/Rapunzel.app"
