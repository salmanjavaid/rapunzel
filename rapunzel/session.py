from __future__ import annotations

import os

if os.name == "nt":
    from rapunzel.session_windows import PTYSession, shell_command
else:
    from rapunzel.session_posix import PTYSession, shell_command

__all__ = ["PTYSession", "shell_command"]
