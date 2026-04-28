from __future__ import annotations

import codecs
import os
import pty
import select
import signal
import subprocess
import termios
import threading
import time
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
    _fd_lock: threading.Lock = field(init=False, default_factory=threading.Lock, repr=False)
    _decoder: codecs.IncrementalDecoder = field(init=False, repr=False)

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
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
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
        if self._reader_thread is not None and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=0.2)

        self._close_master_fd()
        self._terminate_process_group()

    def _close_master_fd(self) -> None:
        with self._fd_lock:
            master_fd = self.master_fd
            self.master_fd = None

        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError:
                pass

    def _terminate_process_group(self) -> None:
        process = self.process
        if process is None or process.poll() is not None:
            return

        pid = process.pid
        signal_plan = (
            (signal.SIGHUP, 0.12),
            (signal.SIGTERM, 0.18),
            (signal.SIGKILL, 0.0),
        )

        for sig, delay in signal_plan:
            try:
                os.killpg(pid, sig)
            except ProcessLookupError:
                return

            deadline = time.monotonic() + delay
            while delay and time.monotonic() < deadline:
                if process.poll() is not None:
                    return
                time.sleep(0.02)

            if process.poll() is not None:
                return

    def _read_loop(self) -> None:
        while True:
            if self._closed.is_set():
                break

            master_fd = self.master_fd
            if master_fd is None:
                break

            try:
                ready, _, _ = select.select([master_fd], [], [], 0.1)
            except (OSError, ValueError):
                break

            if not ready:
                continue

            try:
                chunk = os.read(master_fd, 4096)
            except BlockingIOError:
                continue
            except OSError:
                break

            if not chunk:
                break

            text = self._decoder.decode(chunk)
            if text:
                self.on_output(self.session_id, text)

        final_text = self._decoder.decode(b"", final=True)
        if final_text:
            self.on_output(self.session_id, final_text)

    def _wait_loop(self) -> None:
        assert self.process is not None

        exit_code = self.process.wait()
        self._closed.set()
        self._close_master_fd()
        self.on_exit(self.session_id, exit_code)
