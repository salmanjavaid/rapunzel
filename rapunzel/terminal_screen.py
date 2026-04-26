from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

_deps_path = Path(__file__).resolve().parent.parent / ".deps"
if _deps_path.exists() and str(_deps_path) not in sys.path:
    sys.path.insert(0, str(_deps_path))

import pyte
from wcwidth import wcwidth


@dataclass(slots=True, frozen=True)
class TerminalSnapshot:
    text: str
    cursor_row: int
    cursor_col: int


class TerminalScreen:
    def __init__(self, rows: int = 36, cols: int = 120, max_lines: int = 5000) -> None:
        self.rows = max(2, int(rows))
        self.cols = max(2, int(cols))
        self.max_lines = max(100, int(max_lines))
        self._screen = pyte.HistoryScreen(self.cols, self.rows, history=self.max_lines)
        self._stream = pyte.Stream(self._screen, strict=False)

    def feed(self, text: str) -> str:
        if text:
            self._stream.feed(text)
        return self.render()

    def render(self) -> str:
        return self.snapshot().text

    def append_line(self, text: str) -> str:
        return self.feed(f"{text}\r\n")

    def set_size(self, rows: int, cols: int) -> str:
        next_rows = max(2, int(rows))
        next_cols = max(2, int(cols))
        if next_rows == self.rows and next_cols == self.cols:
            return self.render()

        self.rows = next_rows
        self.cols = next_cols
        self._screen.resize(lines=self.rows, columns=self.cols)
        return self.render()

    def snapshot(self) -> TerminalSnapshot:
        history_lines = [self._render_line(line).rstrip() for line in self._screen.history.top]
        display_lines = [line.rstrip() for line in self._screen.display]
        visible_rows = self._visible_rows(display_lines)
        composed_lines = history_lines + display_lines[:visible_rows]

        overflow = max(0, len(composed_lines) - self.max_lines)
        if overflow:
            composed_lines = composed_lines[overflow:]

        cursor_row = max(0, len(history_lines) + self._screen.cursor.y - overflow)
        cursor_row = min(cursor_row, max(0, len(composed_lines) - 1))
        return TerminalSnapshot(
            text="\r\n".join(composed_lines),
            cursor_row=cursor_row,
            cursor_col=max(0, self._screen.cursor.x),
        )

    def _visible_rows(self, display_lines: list[str]) -> int:
        last_non_empty_row = 0
        for index, line in enumerate(display_lines):
            if line:
                last_non_empty_row = index

        return max(1, self._screen.cursor.y + 1, last_non_empty_row + 1)

    def _render_line(self, line: object) -> str:
        rendered: list[str] = []
        skip_stub = False
        for column in range(self.cols):
            if skip_stub:
                skip_stub = False
                continue

            char = line[column].data
            if not char:
                continue

            width = wcwidth(char[0])
            skip_stub = width == 2
            rendered.append(char)

        return "".join(rendered)
