from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable


OutputCallback = Callable[[str, str], None]
ExitCallback = Callable[[str, int], None]


def shell_command(shell_path: str) -> str:
    return shell_path


def default_shell() -> str:
    return (
        os.environ.get("RAPUNZEL_SHELL")
        or os.environ.get("COMSPEC")
        or r"C:\Windows\System32\cmd.exe"
    )


@dataclass(slots=True)
class PTYSession:
    session_id: str
    cwd: str
    on_output: OutputCallback
    on_exit: ExitCallback
    process: Any = field(init=False, default=None)
    _closed: threading.Event = field(init=False, default_factory=threading.Event, repr=False)
    _reader_thread: threading.Thread | None = field(init=False, default=None, repr=False)
    _wait_thread: threading.Thread | None = field(init=False, default=None, repr=False)
    _rows: int = field(init=False, default=36, repr=False)
    _cols: int = field(init=False, default=120, repr=False)

    def start(self) -> None:
        try:
            from winpty import PtyProcess
        except ImportError as exc:
            raise RuntimeError(
                "Windows terminal support requires pywinpty. "
                "Install it with: python -m pip install pywinpty"
            ) from exc

        env = os.environ.copy()
        env.setdefault("TERM", "xterm-256color")
        env.setdefault("COLORTERM", "truecolor")
        command = shell_command(default_shell())

        try:
            self.process = self._spawn_process(PtyProcess, command, env)
        except Exception:
            self.process = None
            raise

        self.resize(self._rows, self._cols)
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._wait_thread = threading.Thread(target=self._wait_loop, daemon=True)
        self._reader_thread.start()
        self._wait_thread.start()

    def _spawn_process(self, pty_process: Any, command: str, env: dict[str, str]) -> Any:
        spawn_args = {
            "cwd": self.cwd,
            "env": env,
            "dimensions": (self._rows, self._cols),
        }
        try:
            return pty_process.spawn(command, **spawn_args)
        except TypeError:
            process = pty_process.spawn(command)
            self._set_starting_directory(process)
            return process

    def _set_starting_directory(self, process: Any) -> None:
        if not self.cwd:
            return

        shell = default_shell().lower()
        if "powershell" in shell or shell.endswith("pwsh.exe") or shell.endswith("pwsh"):
            escaped = self.cwd.replace("'", "''")
            process.write(f"Set-Location -LiteralPath '{escaped}'\r\n")
            return

        process.write(f'cd /d "{self.cwd}"\r\n')

    def resize(self, rows: int, cols: int) -> None:
        self._rows = max(int(rows), 2)
        self._cols = max(int(cols), 2)
        process = self.process
        if process is None:
            return

        resize = getattr(process, "setwinsize", None)
        if callable(resize):
            resize(self._rows, self._cols)
            return

        set_size = getattr(process, "set_size", None)
        if callable(set_size):
            set_size(self._cols, self._rows)

    def send(self, data: bytes) -> None:
        process = self.process
        if process is None or self._closed.is_set():
            return

        try:
            process.write(data.decode("utf-8", errors="replace"))
        except Exception:
            self.close()

    def close(self) -> None:
        if self._closed.is_set():
            return

        self._closed.set()
        self._terminate_process()
        if self._reader_thread is not None and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=0.2)

    def _terminate_process(self) -> None:
        process = self.process
        if process is None:
            return

        for method_name, args in (
            ("close", (True,)),
            ("terminate", (True,)),
            ("kill", ()),
            ("close", ()),
            ("terminate", ()),
        ):
            method = getattr(process, method_name, None)
            if not callable(method):
                continue
            try:
                method(*args)
                return
            except TypeError:
                continue
            except Exception:
                return

    def _read_loop(self) -> None:
        process = self.process
        if process is None:
            return

        while not self._closed.is_set():
            try:
                chunk = process.read(4096)
            except TypeError:
                try:
                    chunk = process.read()
                except EOFError:
                    break
                except Exception:
                    break
            except EOFError:
                break
            except Exception:
                break

            if not chunk:
                if not self._is_alive(process):
                    break
                time.sleep(0.02)
                continue

            if isinstance(chunk, bytes):
                text = chunk.decode("utf-8", errors="replace")
            else:
                text = str(chunk)
            if text:
                self.on_output(self.session_id, text)

    def _wait_loop(self) -> None:
        process = self.process
        if process is None:
            return

        while not self._closed.is_set() and self._is_alive(process):
            time.sleep(0.1)

        self._closed.set()
        self.on_exit(self.session_id, self._exit_code(process))

    def _is_alive(self, process: Any) -> bool:
        isalive = getattr(process, "isalive", None)
        if callable(isalive):
            try:
                return bool(isalive())
            except Exception:
                return False
        return not self._closed.is_set()

    def _exit_code(self, process: Any) -> int:
        exitstatus = getattr(process, "exitstatus", None)
        if isinstance(exitstatus, int):
            return exitstatus
        status = getattr(process, "status", None)
        if isinstance(status, int):
            return status
        return 0
