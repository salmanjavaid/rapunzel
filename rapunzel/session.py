from __future__ import annotations

import os
import pty
import signal
import subprocess
import termios
import threading
from dataclasses import dataclass, field
from fcntl import ioctl
from typing import Callable


OutputCallback = Callable[[str, str], None]
ExitCallback = Callable[[str, int], None]


def shell_command(shell_path: str) -> list[str]:
    shell_name = os.path.basename(shell_path)
    if shell_name in {"bash", "zsh", "sh", "ksh"}:
        return [shell_path, "-l", "-i"]
    if shell_name == "fish":
        return [shell_path, "-i"]
    return [shell_path]


@dataclass(slots=True)
class PTYSession:
    session_id: str
    cwd: str
    on_output: OutputCallback
    on_exit: ExitCallback
    master_fd: int | None = field(init=False, default=None)
    process: subprocess.Popen[bytes] | None = field(init=False, default=None)
    _closed: threading.Event = field(init=False, default_factory=threading.Event, repr=False)
    _reader_thread: threading.Thread | None = field(init=False, default=None, repr=False)
    _wait_thread: threading.Thread | None = field(init=False, default=None, repr=False)

    def start(self) -> None:
        master_fd, slave_fd = pty.openpty()
        env = os.environ.copy()
        env.setdefault("TERM", "xterm-256color")
        env.setdefault("COLORTERM", "truecolor")
        shell_path = env.get("SHELL", "/bin/zsh")

        try:
            process = subprocess.Popen(
                shell_command(shell_path),
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=self.cwd,
                env=env,
                close_fds=True,
                start_new_session=True,
            )
        except Exception:
            os.close(master_fd)
            os.close(slave_fd)
            raise

        os.close(slave_fd)
        self.master_fd = master_fd
        self.process = process
        self.resize(36, 120)

        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._wait_thread = threading.Thread(target=self._wait_loop, daemon=True)
        self._reader_thread.start()
        self._wait_thread.start()

    def resize(self, rows: int, cols: int) -> None:
        if self.master_fd is None:
            return

        winsize = rows.to_bytes(2, "little") + cols.to_bytes(2, "little") + b"\0" * 4
        ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

    def send(self, data: bytes) -> None:
        if self.master_fd is None or self._closed.is_set():
            return

        try:
            os.write(self.master_fd, data)
        except OSError:
            self.close()

    def close(self) -> None:
        if self._closed.is_set():
            return

        self._closed.set()
        if self.process is not None and self.process.poll() is None:
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None

    def _read_loop(self) -> None:
        assert self.master_fd is not None

        while not self._closed.is_set():
            try:
                chunk = os.read(self.master_fd, 4096)
            except OSError:
                break

            if not chunk:
                break

            self.on_output(self.session_id, chunk.decode("utf-8", errors="replace"))

    def _wait_loop(self) -> None:
        assert self.process is not None

        exit_code = self.process.wait()
        self._closed.set()
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        self.on_exit(self.session_id, exit_code)
