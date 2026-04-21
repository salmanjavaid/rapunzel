from __future__ import annotations

import json
import os
import platform
import sys
import threading
from pathlib import Path
from typing import Any

_deps_path = Path(__file__).resolve().parent.parent / ".deps"
if _deps_path.exists() and str(_deps_path) not in sys.path:
    sys.path.insert(0, str(_deps_path))

if platform.system() == "Darwin":
    os.environ.setdefault("QT_API", "pyside6")
    os.environ.setdefault("PYWEBVIEW_GUI", "qt")

import webview

from rapunzel.state import AppState
from rapunzel.store import WorkspaceStore


def app_icon_path() -> str | None:
    path = Path(__file__).resolve().parent.parent / "icon.png"
    return str(path) if path.exists() else None


def configure_app_icon(icon_path: str | None) -> None:
    if not icon_path:
        return

    try:
        from qtpy.QtGui import QIcon
        from qtpy.QtWidgets import QApplication

        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName("Rapunzel")
        if hasattr(app, "setApplicationDisplayName"):
            app.setApplicationDisplayName("Rapunzel")
        if hasattr(app, "setDesktopFileName"):
            app.setDesktopFileName("local.rapunzel.desktop")

        icon = QIcon(icon_path)
        if not icon.isNull():
            app.setWindowIcon(icon)
    except Exception:
        pass

    if platform.system() != "Darwin":
        return

    try:
        import AppKit

        image = AppKit.NSImage.alloc().initWithContentsOfFile_(icon_path)
        if image is not None:
            AppKit.NSApplication.sharedApplication().setApplicationIconImage_(image)
    except Exception:
        pass


class RapunzelBridge:
    def __init__(self) -> None:
        self._store = WorkspaceStore()
        self._window: webview.Window | None = None
        self._js_ready = threading.Event()
        self._output_lock = threading.Lock()
        self._output_buf: dict[str, list[str]] = {}
        self._flush_scheduled = False
        self._state = AppState(
            self._store,
            push_output=self._push_output,
            push_exit=self._push_exit,
        )
        self._state.bootstrap()

    def set_window(self, window: webview.Window) -> None:
        self._window = window

    # ------------------------------------------------------------------
    # Push: PTY → JS (like VS Code's onData → xterm.write)
    # ------------------------------------------------------------------

    def signal_ready(self) -> None:
        """Called from JS once the page is loaded and push handlers exist."""
        self._js_ready.set()

    def _push_output(self, session_id: str, data: str) -> None:
        if not self._js_ready.is_set() or self._window is None:
            return

        with self._output_lock:
            self._output_buf.setdefault(session_id, []).append(data)
            if self._flush_scheduled:
                return
            self._flush_scheduled = True

        timer = threading.Timer(0.016, self._flush_output)  # ~60 fps
        timer.daemon = True
        timer.start()

    def _flush_output(self) -> None:
        with self._output_lock:
            pending = self._output_buf
            self._output_buf = {}
            self._flush_scheduled = False

        if self._window is None:
            return

        for session_id, chunks in pending.items():
            merged = "".join(chunks)
            try:
                js = f"window.__rapunzelPtyOutput({json.dumps(session_id)},{json.dumps(merged)})"
                self._window.evaluate_js(js)
            except Exception:
                pass

    def _push_exit(self, session_id: str, exit_code: int) -> None:
        if not self._js_ready.is_set() or self._window is None:
            return
        try:
            js = f"window.__rapunzelPtyExit({json.dumps(session_id)},{json.dumps(int(exit_code))})"
            self._window.evaluate_js(js)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Bridge methods (called from JS)
    # ------------------------------------------------------------------

    def get_ui_state(self) -> dict[str, object]:
        return self._ui_payload()

    def poll_events(self) -> list[dict[str, str | int]]:
        return self._state.drain_events()

    def get_session_transcript(self, session_id: str | None) -> str:
        return self._state.session_stream(session_id)

    def get_session_snapshot(self, session_id: str | None) -> str:
        return self._state.session_snapshot(session_id)

    def select_session(self, session_id: str | None) -> dict[str, object]:
        self._state.select(session_id)
        return self._ui_payload()

    def create_root(self) -> dict[str, object]:
        self._state.create_root_session()
        return self._ui_payload()

    def create_child(self) -> dict[str, object]:
        self._state.create_child_session()
        return self._ui_payload()

    def create_child_under(self, session_id: str | None) -> dict[str, object]:
        self._state.create_child_session_under(session_id)
        return self._ui_payload()

    def rename_session(self, session_id: str, title: str) -> dict[str, object]:
        self._state.rename(session_id, title)
        return self._ui_payload()

    def move_session(self, session_id: str, direction: str) -> dict[str, object]:
        if direction in {"up", "down"}:
            self._state.move(session_id, direction)
        return self._ui_payload()

    def toggle_collapsed(self, session_id: str) -> dict[str, object]:
        node = self._state.node_by_id(session_id)
        if node is None:
            return self._ui_payload()

        self._state.set_collapsed(session_id, not node.is_collapsed)
        return self._ui_payload()

    def close_session(self, session_id: str) -> dict[str, object]:
        self._state.close(session_id)
        return self._ui_payload()

    def close_branch(self, session_id: str) -> dict[str, object]:
        self._state.close_branch(session_id)
        return self._ui_payload()

    def send_input(self, session_id: str | None, data: str) -> None:
        if session_id is None or not data:
            return
        self._state.send_input(session_id, data.encode("utf-8"))

    def resize_session(self, session_id: str | None, rows: int, cols: int) -> None:
        if session_id is None:
            return
        self._state.resize_session(session_id, max(int(rows), 2), max(int(cols), 2))

    def shutdown(self, *args: Any, **kwargs: Any) -> None:
        _ = args, kwargs
        self._state.shutdown()

    def _ui_payload(self) -> dict[str, object]:
        payload = self._state.ui_state()
        payload["selected"] = self._selected_payload()
        return payload

    def _selected_payload(self) -> dict[str, str] | None:
        node = self._state.node_by_id(self._state.selected_session_id)
        if node is None:
            return None

        return {
            "id": node.id,
            "title": node.title,
            "status": self._state.statuses.get(node.id, "idle"),
            "is_collapsed": node.is_collapsed,
            "initial_cwd": node.initial_cwd,
            "cwd": node.last_known_cwd or node.initial_cwd,
        }


def main() -> None:
    webview.settings["ALLOW_FILE_URLS"] = True

    bridge = RapunzelBridge()
    icon = app_icon_path()
    configure_app_icon(icon)
    index_path = Path(__file__).resolve().parent.parent / "webui" / "dist" / "index.html"
    window = webview.create_window(
        "Rapunzel",
        url=str(index_path),
        js_api=bridge,
        width=1024,
        height=768,
        min_size=(800, 600),
        background_color="#dfe6ef",
        text_select=True,
    )
    if window is not None:
        bridge.set_window(window)
        window.events.closed += bridge.shutdown

    webview.start(http_server=True, private_mode=True, icon=icon)
