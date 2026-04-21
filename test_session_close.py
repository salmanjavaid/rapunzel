import time
import unittest

from rapunzel.session import PTYSession


class PTYSessionCloseTest(unittest.TestCase):
    def test_close_returns_when_foreground_child_ignores_sigterm(self) -> None:
        session = PTYSession("close-test", ".", lambda *_: None, lambda *_: None)
        session.start()
        time.sleep(0.5)

        session.send(
            b'python3 -c "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print(123); time.sleep(30)"\n'
        )
        time.sleep(0.8)

        started = time.monotonic()
        session.close()
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 1.5)
        self.assertIsNotNone(session.process)
        self.assertIsNotNone(session.process.poll())


if __name__ == "__main__":
    unittest.main()
