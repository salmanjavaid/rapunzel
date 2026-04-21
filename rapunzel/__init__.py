from __future__ import annotations

import sys
from pathlib import Path


_deps_path = Path(__file__).resolve().parent.parent / ".deps"
if _deps_path.exists():
    sys.path.insert(0, str(_deps_path))

__all__ = ["__version__"]

__version__ = "0.1.0"
