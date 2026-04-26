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

    def test_snapshot_uses_crlf_line_separators(self) -> None:
        screen = TerminalScreen(rows=5, cols=20)
        screen.feed("line1\r\nline2\r\nline3\r\n")
        snapshot = screen.snapshot()

        # Lines should be joined with \r\n for xterm.js compatibility
        self.assertIn("\r\n", snapshot.text)
        # Should NOT contain bare \n (without preceding \r)
        cleaned = snapshot.text.replace("\r\n", "")
        self.assertNotIn("\n", cleaned)

    def test_append_line(self) -> None:
        screen = TerminalScreen(rows=4, cols=40)
        result = screen.append_line("[process exited with code 0]")
        self.assertIn("[process exited with code 0]", result)

    def test_max_lines_overflow_trims_oldest(self) -> None:
        max_lines = 100
        screen = TerminalScreen(rows=3, cols=20, max_lines=max_lines)
        for i in range(200):
            screen.feed(f"line{i}\r\n")

        snapshot = screen.snapshot()
        lines = [l for l in snapshot.text.split("\r\n") if l.strip()]
        # Total lines should not exceed max_lines
        self.assertLessEqual(len(lines), max_lines)
        # Should contain the latest lines
        self.assertIn("line199", snapshot.text)

    def test_set_size_noop_when_same(self) -> None:
        screen = TerminalScreen(rows=10, cols=80)
        screen.feed("hello")
        result = screen.set_size(10, 80)
        self.assertIn("hello", result)

    def test_minimum_dimensions_enforced(self) -> None:
        screen = TerminalScreen(rows=1, cols=1)
        self.assertEqual(screen.rows, 2)
        self.assertEqual(screen.cols, 2)

    def test_snapshot_cursor_position(self) -> None:
        screen = TerminalScreen(rows=5, cols=20)
        screen.feed("hello")
        snapshot = screen.snapshot()
        self.assertEqual(snapshot.cursor_row, 0)
        self.assertEqual(snapshot.cursor_col, 5)

    def test_empty_screen_renders(self) -> None:
        screen = TerminalScreen(rows=4, cols=20)
        snapshot = screen.snapshot()
        self.assertEqual(snapshot.cursor_row, 0)
        self.assertEqual(snapshot.cursor_col, 0)


if __name__ == "__main__":
    unittest.main()
