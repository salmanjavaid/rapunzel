#!/bin/bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE_ICON="$REPO_DIR/icon.png"
OUTPUT_DIR="$REPO_DIR/.build-assets"
ICONSET_DIR="$OUTPUT_DIR/AppIcon.iconset"
ICNS_PATH="$OUTPUT_DIR/AppIcon.icns"

if [[ ! -f "$SOURCE_ICON" ]]; then
  echo "Missing source icon: $SOURCE_ICON" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
rm -f "$ICNS_PATH"

generate_with_pillow() {
  local mode="$1"
  if [[ "$mode" == "arm64" ]]; then
    arch -arm64 python3 - <<'PY' "$SOURCE_ICON" "$ICNS_PATH"
from pathlib import Path
import sys

from PIL import Image

source_icon = Path(sys.argv[1])
target_icon = Path(sys.argv[2])
image = Image.open(source_icon).convert("RGBA")
image.save(target_icon, format="ICNS")
PY
    return
  fi

  python3 - <<'PY' "$SOURCE_ICON" "$ICNS_PATH"
from pathlib import Path
import sys

from PIL import Image

source_icon = Path(sys.argv[1])
target_icon = Path(sys.argv[2])
image = Image.open(source_icon).convert("RGBA")
image.save(target_icon, format="ICNS")
PY
}

if arch -arm64 python3 - <<'PY' >/dev/null 2>&1
from PIL import Image
PY
then
  generate_with_pillow "arm64"
elif python3 - <<'PY' >/dev/null 2>&1
from PIL import Image
PY
then
  generate_with_pillow "default"
else
  rm -rf "$ICONSET_DIR"
  mkdir -p "$ICONSET_DIR"

  sizes=(16 32 128 256 512)
  for size in "${sizes[@]}"; do
    retina_size=$((size * 2))
    sips -z "$size" "$size" "$SOURCE_ICON" --out "$ICONSET_DIR/icon_${size}x${size}.png" >/dev/null
    sips -z "$retina_size" "$retina_size" "$SOURCE_ICON" --out "$ICONSET_DIR/icon_${size}x${size}@2x.png" >/dev/null
  done

  iconutil -c icns "$ICONSET_DIR" -o "$ICNS_PATH"
fi

echo "Generated: $ICNS_PATH"
