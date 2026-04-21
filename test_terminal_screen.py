import unittest

from rapunzel.terminal_screen import TerminalScreen


class TerminalScreenTest(unittest.TestCase):
    def test_overwrite_sequences_render_final_line(self) -> None:
        screen = TerminalScreen(rows=4, cols=20)

        rendered = screen.feed("hello\r\x1b[Kbye")

        self.assertEqual(rendered, "bye")

    def test_history_snapshot_keeps_scrollback(self) -> None:
        screen = TerminalScreen(rows=3, cols=12, max_lines=20)

        screen.feed("one\r\ntwo\r\nthree\r\nfour\r\n")
        snapshot = screen.snapshot()

        self.assertIn("one", snapshot.text)
        self.assertIn("four", snapshot.text)

    def test_resize_updates_dimensions_without_losing_rendered_text(self) -> None:
        screen = TerminalScreen(rows=4, cols=20)
        screen.feed("prompt> hello")

        resized = screen.set_size(6, 30)

        self.assertEqual(screen.rows, 6)
        self.assertEqual(screen.cols, 30)
        self.assertIn("prompt> hello", resized)


if __name__ == "__main__":
    unittest.main()
