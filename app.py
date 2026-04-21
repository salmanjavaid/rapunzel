import sys
from pathlib import Path

_deps_path = Path(__file__).resolve().parent / ".deps"
if _deps_path.exists() and str(_deps_path) not in sys.path:
    sys.path.insert(0, str(_deps_path))

try:
    from rapunzel.web_ui import main
except Exception:
    from rapunzel.ui import main


if __name__ == "__main__":
    main()
