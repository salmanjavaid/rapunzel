import os
import unittest

from rapunzel import session
from rapunzel.session_windows import PTYSession as WindowsPTYSession
from rapunzel.session_windows import shell_command as windows_shell_command

if os.name != "nt":
    from rapunzel.session_posix import shell_command as posix_shell_command
else:
    posix_shell_command = None


class SessionPlatformTest(unittest.TestCase):
    def test_public_session_selects_current_platform_backend(self) -> None:
        expected_module = "rapunzel.session_windows" if os.name == "nt" else "rapunzel.session_posix"
        self.assertEqual(session.PTYSession.__module__, expected_module)

    def test_posix_shell_command_keeps_login_interactive_shells(self) -> None:
        if posix_shell_command is None:
            self.skipTest("POSIX shell command test does not run on Windows")
        self.assertEqual(posix_shell_command("/bin/zsh"), ["/bin/zsh", "-l", "-i"])
        self.assertEqual(posix_shell_command("/bin/sh"), ["/bin/sh", "-i"])
        self.assertEqual(posix_shell_command("/bin/fish"), ["/bin/fish", "-i"])
        self.assertEqual(posix_shell_command("/custom/shell"), ["/custom/shell"])

    def test_windows_shell_command_passthrough(self) -> None:
        self.assertEqual(windows_shell_command(r"C:\Windows\System32\cmd.exe"), r"C:\Windows\System32\cmd.exe")

    def test_windows_resize_supports_pywinpty_style_methods(self) -> None:
        session = WindowsPTYSession("win-test", ".", lambda *_: None, lambda *_: None)
        winsize_process = _FakeWindowsProcess()
        session.process = winsize_process

        session.resize(40, 100)
        self.assertEqual(winsize_process.winsize, (40, 100))

        size_process = _FakeWindowsSetSizeProcess()
        session.process = size_process
        session.resize(30, 90)
        self.assertEqual(size_process.size, (90, 30))

    def test_windows_send_writes_text(self) -> None:
        session = WindowsPTYSession("win-test", ".", lambda *_: None, lambda *_: None)
        process = _FakeWindowsProcess()
        session.process = process

        session.send("hello".encode("utf-8"))

        self.assertEqual(process.writes[-1], "hello")


class _FakeWindowsProcess:
    def __init__(self) -> None:
        self.writes = []
        self.winsize = None
        self.size = None

    def write(self, data: str) -> None:
        self.writes.append(data)

    def setwinsize(self, rows: int, cols: int) -> None:
        self.winsize = (rows, cols)

    def set_size(self, cols: int, rows: int) -> None:
        self.size = (cols, rows)


class _FakeWindowsSetSizeProcess:
    def __init__(self) -> None:
        self.size = None

    def set_size(self, cols: int, rows: int) -> None:
        self.size = (cols, rows)


if __name__ == "__main__":
    unittest.main()
