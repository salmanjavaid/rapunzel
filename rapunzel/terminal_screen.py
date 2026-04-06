from __future__ import annotations

from dataclasses import dataclass, field


ESC = "\x1b"


@dataclass(slots=True)
class TerminalScreen:
    max_lines: int = 5000
    lines: list[list[str]] = field(default_factory=lambda: [[]])
    cursor_row: int = 0
    cursor_col: int = 0
    saved_cursor_row: int = 0
    saved_cursor_col: int = 0

    def feed(self, text: str) -> str:
        index = 0
        while index < len(text):
            char = text[index]

            if char == ESC:
                next_index = self._consume_escape(text, index)
                if next_index > index:
                    index = next_index
                    continue

            if char == "\n":
                self.cursor_row += 1
                self.cursor_col = 0
                self._ensure_row(self.cursor_row)
            elif char == "\r":
                self.cursor_col = 0
            elif char == "\b":
                self.cursor_col = max(0, self.cursor_col - 1)
            elif char == "\t":
                spaces = 8 - (self.cursor_col % 8)
                for _ in range(spaces):
                    self._put_char(" ")
            elif char >= " ":
                self._put_char(char)

            index += 1

        return self.render()

    def render(self) -> str:
        return "\n".join("".join(line).rstrip() for line in self.lines)

    def append_line(self, text: str) -> str:
        return self.feed(text + "\n")

    def _put_char(self, char: str) -> None:
        self._ensure_row(self.cursor_row)
        line = self.lines[self.cursor_row]
        while len(line) < self.cursor_col:
            line.append(" ")

        if self.cursor_col == len(line):
            line.append(char)
        else:
            line[self.cursor_col] = char

        self.cursor_col += 1

    def _ensure_row(self, row: int) -> None:
        while len(self.lines) <= row:
            self.lines.append([])

        overflow = len(self.lines) - self.max_lines
        if overflow > 0:
            del self.lines[:overflow]
            self.cursor_row = max(0, self.cursor_row - overflow)
            self.saved_cursor_row = max(0, self.saved_cursor_row - overflow)

    def _consume_escape(self, text: str, index: int) -> int:
        if index + 1 >= len(text):
            return len(text)

        next_char = text[index + 1]
        if next_char == "[":
            cursor = index + 2
            while cursor < len(text):
                final = text[cursor]
                if "@" <= final <= "~":
                    self._apply_csi(text[index + 2 : cursor], final)
                    return cursor + 1
                cursor += 1
            return len(text)

        if next_char == "]":
            cursor = index + 2
            while cursor < len(text):
                if text[cursor] == "\x07":
                    return cursor + 1
                if text[cursor] == ESC and cursor + 1 < len(text) and text[cursor + 1] == "\\":
                    return cursor + 2
                cursor += 1
            return len(text)

        if next_char == "7":
            self.saved_cursor_row = self.cursor_row
            self.saved_cursor_col = self.cursor_col
            return index + 2

        if next_char == "8":
            self.cursor_row = self.saved_cursor_row
            self.cursor_col = self.saved_cursor_col
            self._ensure_row(self.cursor_row)
            return index + 2

        return index + 2

    def _apply_csi(self, params: str, final: str) -> None:
        normalized = params.lstrip("?")
        parts = normalized.split(";") if normalized else []

        def number(position: int, default: int) -> int:
            if position >= len(parts) or parts[position] == "":
                return default
            try:
                return int(parts[position])
            except ValueError:
                return default

        if final == "A":
            self.cursor_row = max(0, self.cursor_row - number(0, 1))
        elif final == "B":
            self.cursor_row += number(0, 1)
            self._ensure_row(self.cursor_row)
        elif final == "C":
            self.cursor_col += number(0, 1)
        elif final == "D":
            self.cursor_col = max(0, self.cursor_col - number(0, 1))
        elif final == "E":
            self.cursor_row += number(0, 1)
            self.cursor_col = 0
            self._ensure_row(self.cursor_row)
        elif final == "F":
            self.cursor_row = max(0, self.cursor_row - number(0, 1))
            self.cursor_col = 0
        elif final == "G":
            self.cursor_col = max(0, number(0, 1) - 1)
        elif final in {"H", "f"}:
            self.cursor_row = max(0, number(0, 1) - 1)
            self.cursor_col = max(0, number(1, 1) - 1)
            self._ensure_row(self.cursor_row)
        elif final == "J":
            mode = number(0, 0)
            if mode == 2:
                self.lines = [[]]
                self.cursor_row = 0
                self.cursor_col = 0
            elif mode == 0:
                self._erase_to_screen_end()
            elif mode == 1:
                self._erase_to_screen_start()
        elif final == "K":
            self._erase_in_line(number(0, 0))
        elif final == "s":
            self.saved_cursor_row = self.cursor_row
            self.saved_cursor_col = self.cursor_col
        elif final == "u":
            self.cursor_row = self.saved_cursor_row
            self.cursor_col = self.saved_cursor_col
            self._ensure_row(self.cursor_row)

    def _erase_in_line(self, mode: int) -> None:
        self._ensure_row(self.cursor_row)
        line = self.lines[self.cursor_row]
        if mode == 2:
            self.lines[self.cursor_row] = []
        elif mode == 1:
            upto = min(self.cursor_col + 1, len(line))
            for index in range(upto):
                line[index] = " "
        else:
            if self.cursor_col < len(line):
                del line[self.cursor_col :]

    def _erase_to_screen_end(self) -> None:
        self._erase_in_line(0)
        if self.cursor_row + 1 < len(self.lines):
            del self.lines[self.cursor_row + 1 :]

    def _erase_to_screen_start(self) -> None:
        for row in range(self.cursor_row):
            self.lines[row] = []
        self._erase_in_line(1)
