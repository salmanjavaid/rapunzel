from __future__ import annotations

import os
import queue
import re
import threading
import uuid
from dataclasses import dataclass
from typing import Callable, Literal
from urllib.parse import unquote, urlparse

from rapunzel.models import SessionNode, WorkspaceSnapshot, utc_now
from rapunzel.session import PTYSession
from rapunzel.store import WorkspaceStore
from rapunzel.terminal_screen import TerminalScreen


@dataclass(slots=True)
class SessionEvent:
    kind: Literal["output", "exit"]
    session_id: str
    payload: str | int


class AppState:
    _osc7_pattern = re.compile(r"\x1b]7;([^\x07\x1b]+)(?:\x07|\x1b\\)")

    def __init__(
        self,
        store: WorkspaceStore,
        push_output: Callable[[str, str], None] | None = None,
        push_exit: Callable[[str, int], None] | None = None,
    ) -> None:
        self.store = store
        self.tree: list[SessionNode] = []
        self.selected_session_id: str | None = None
        self.terminal_buffers: dict[str, str] = {}
        self.terminal_streams: dict[str, str] = {}
        self.terminal_screens: dict[str, TerminalScreen] = {}
        self.statuses: dict[str, str] = {}
        self.sessions: dict[str, PTYSession] = {}
        self.event_queue: queue.Queue[SessionEvent] = queue.Queue()
        self.next_shell_number = 1
        self._push_output = push_output
        self._push_exit = push_exit

    def bootstrap(self) -> None:
        snapshot = self.store.load()
        self.tree = snapshot.nodes
        self.selected_session_id = snapshot.selected_session_id
        self.next_shell_number = snapshot.next_shell_number

        if self.selected_session_id not in {node.id for node in self.tree}:
            self.selected_session_id = self.visible_nodes()[0].id if self.tree else None

        for node in self.tree:
            self.terminal_screens[node.id] = TerminalScreen()
            self.terminal_buffers[node.id] = ""
            self.terminal_streams[node.id] = ""
            self.statuses[node.id] = "starting"
            self._start_runtime(node)

    def snapshot(self) -> WorkspaceSnapshot:
        return WorkspaceSnapshot(
            nodes=self.tree,
            selected_session_id=self.selected_session_id,
            next_shell_number=self.next_shell_number,
        )

    def persist(self) -> None:
        self.store.save(self.snapshot())

    def shutdown(self) -> None:
        self.persist()
        for session in list(self.sessions.values()):
            session.close()
        self.sessions.clear()

    def node_by_id(self, session_id: str | None) -> SessionNode | None:
        if session_id is None:
            return None
        return next((node for node in self.tree if node.id == session_id), None)

    def child_nodes(self, parent_id: str | None) -> list[SessionNode]:
        return sorted(
            [node for node in self.tree if node.parent_id == parent_id],
            key=lambda node: node.order_index,
        )

    def visible_nodes(self, parent_id: str | None = None) -> list[SessionNode]:
        nodes: list[SessionNode] = []
        for child in self.child_nodes(parent_id):
            nodes.append(child)
            if not child.is_collapsed:
                nodes.extend(self.visible_nodes(child.id))
        return nodes

    def create_root_session(self) -> str:
        return self._create_session(parent_id=None)

    def create_child_session(self) -> str | None:
        if self.selected_session_id is None:
            return None
        return self._create_session(parent_id=self.selected_session_id)

    def create_child_session_under(self, parent_id: str | None) -> str | None:
        if parent_id is None:
            return None
        if self.node_by_id(parent_id) is None:
            return None
        return self._create_session(parent_id=parent_id)

    def select(self, session_id: str | None) -> None:
        self.selected_session_id = session_id
        self.persist()

    def rename(self, session_id: str, title: str) -> None:
        node = self.node_by_id(session_id)
        if node is None:
            return

        cleaned = title.strip()
        if not cleaned:
            return

        node.title = cleaned
        node.updated_at = utc_now()
        self.persist()

    def set_collapsed(self, session_id: str, collapsed: bool) -> None:
        node = self.node_by_id(session_id)
        if node is None:
            return

        node.is_collapsed = collapsed
        node.updated_at = utc_now()
        self.persist()

    def move(self, session_id: str, direction: Literal["up", "down"]) -> None:
        node = self.node_by_id(session_id)
        if node is None:
            return

        siblings = self.child_nodes(node.parent_id)
        current_index = next((index for index, item in enumerate(siblings) if item.id == session_id), None)
        if current_index is None:
            return

        target_index = current_index - 1 if direction == "up" else current_index + 1
        if target_index < 0 or target_index >= len(siblings):
            return

        siblings[current_index].order_index, siblings[target_index].order_index = (
            siblings[target_index].order_index,
            siblings[current_index].order_index,
        )
        siblings[current_index].updated_at = utc_now()
        siblings[target_index].updated_at = utc_now()
        self.persist()

    def move_relative_to_target(
        self,
        session_id: str,
        target_id: str | None,
        drop_mode: Literal["root", "sibling", "child"],
    ) -> bool:
        node = self.node_by_id(session_id)
        if node is None:
            return False

        if drop_mode == "root" or target_id is None:
            return self._move_to_parent(session_id, None, len(self.child_nodes(None)))

        target = self.node_by_id(target_id)
        if target is None or target.id == session_id:
            return False

        if drop_mode == "child":
            return self._move_to_parent(session_id, target.id, len(self.child_nodes(target.id)))

        siblings = self.child_nodes(target.parent_id)
        target_index = next((index for index, item in enumerate(siblings) if item.id == target.id), None)
        if target_index is None:
            return False

        insert_index = target_index + 1
        source_index = next((index for index, item in enumerate(siblings) if item.id == session_id), None)
        if node.parent_id == target.parent_id and source_index is not None and source_index < insert_index:
            insert_index -= 1

        return self._move_to_parent(session_id, target.parent_id, insert_index)

    def close(self, session_id: str) -> None:
        node = self.node_by_id(session_id)
        if node is None:
            return

        session = self.sessions.pop(session_id, None)

        children = self.child_nodes(node.id)
        self.tree = [item for item in self.tree if item.id != session_id]
        for child in children:
            child.parent_id = node.parent_id
            child.updated_at = utc_now()

        self._normalize_order(node.parent_id)
        self.terminal_buffers.pop(session_id, None)
        self.terminal_streams.pop(session_id, None)
        self.terminal_screens.pop(session_id, None)
        self.statuses.pop(session_id, None)

        if self.selected_session_id == session_id:
            self.selected_session_id = self.visible_nodes()[0].id if self.tree else None

        self.persist()
        self._close_runtime_async(session)

    def close_branch(self, session_id: str) -> None:
        node = self.node_by_id(session_id)
        if node is None:
            return

        closing_ids = {node.id, *self._descendant_ids(node.id)}
        closing_sessions: list[PTYSession] = []
        for closing_id in closing_ids:
            session = self.sessions.pop(closing_id, None)
            if session is not None:
                closing_sessions.append(session)

            self.terminal_buffers.pop(closing_id, None)
            self.terminal_streams.pop(closing_id, None)
            self.terminal_screens.pop(closing_id, None)
            self.statuses.pop(closing_id, None)

        self.tree = [item for item in self.tree if item.id not in closing_ids]
        self._normalize_order(node.parent_id)

        if self.selected_session_id in closing_ids:
            self.selected_session_id = self.visible_nodes()[0].id if self.tree else None

        self.persist()
        for session in closing_sessions:
            self._close_runtime_async(session)

    def send_input_to_selected_session(self, data: bytes) -> None:
        if self.selected_session_id is None:
            return

        self.send_input(self.selected_session_id, data)

    def send_input(self, session_id: str, data: bytes) -> None:
        session = self.sessions.get(session_id)
        if session is not None:
            session.send(data)

    def resize_selected_session(self, rows: int, cols: int) -> None:
        if self.selected_session_id is None:
            return

        self.resize_session(self.selected_session_id, rows, cols)

    def resize_session(self, session_id: str, rows: int, cols: int) -> None:
        screen = self.terminal_screens.get(session_id)
        if screen is not None:
            self.terminal_buffers[session_id] = screen.set_size(rows, cols)

        session = self.sessions.get(session_id)
        if session is not None:
            session.resize(rows, cols)

    def apply_output(self, session_id: str, chunk: str) -> str:
        screen = self.terminal_screens.setdefault(session_id, TerminalScreen())
        rendered = screen.feed(chunk)
        self.terminal_buffers[session_id] = rendered
        self.terminal_streams[session_id] = self.terminal_streams.get(session_id, "") + chunk
        self._update_last_known_cwd(session_id, chunk)
        if session_id in self.statuses and self.statuses[session_id] != "error":
            self.statuses[session_id] = "running"
        return rendered

    def apply_exit(self, session_id: str, exit_code: int) -> str:
        message = f"\n[process exited with code {exit_code}]\n"
        screen = self.terminal_screens.setdefault(session_id, TerminalScreen())
        self.terminal_buffers[session_id] = screen.append_line(message.rstrip("\n"))
        self.terminal_streams[session_id] = self.terminal_streams.get(session_id, "") + message
        self.statuses[session_id] = f"exited {exit_code}"
        self.sessions.pop(session_id, None)
        return self.terminal_buffers[session_id]

    def _create_session(self, parent_id: str | None) -> str:
        parent = self.node_by_id(parent_id)
        initial_cwd = (
            parent.last_known_cwd
            if parent is not None and parent.last_known_cwd
            else os.getcwd() if parent_id is None
            else parent.initial_cwd
        )

        session_id = str(uuid.uuid4())
        node = SessionNode(
            id=session_id,
            parent_id=parent_id,
            title=f"Shell {self.next_shell_number}",
            order_index=len(self.child_nodes(parent_id)),
            is_collapsed=False,
            initial_cwd=initial_cwd,
            last_known_cwd=initial_cwd,
        )

        self.tree.append(node)
        self.terminal_screens[session_id] = TerminalScreen()
        self.terminal_buffers[session_id] = ""
        self.terminal_streams[session_id] = ""
        self.statuses[session_id] = "starting"
        self.selected_session_id = session_id
        self.next_shell_number += 1

        if parent is not None:
            parent.is_collapsed = False
            parent.updated_at = utc_now()

        self._start_runtime(node)
        self.persist()
        return session_id

    def _start_runtime(self, node: SessionNode) -> None:
        push_output = self._push_output
        push_exit = self._push_exit

        def on_output(session_id: str, chunk: str) -> None:
            self.event_queue.put(SessionEvent("output", session_id, chunk))
            if push_output is not None:
                push_output(session_id, chunk)

        def on_exit(session_id: str, code: int) -> None:
            self.event_queue.put(SessionEvent("exit", session_id, code))
            if push_exit is not None:
                push_exit(session_id, code)

        runtime = PTYSession(
            session_id=node.id,
            cwd=node.last_known_cwd or node.initial_cwd,
            on_output=on_output,
            on_exit=on_exit,
        )

        try:
            runtime.start()
        except Exception as exc:
            self.statuses[node.id] = "error"
            screen = self.terminal_screens.setdefault(node.id, TerminalScreen())
            message = f"[failed to start shell: {exc}]"
            self.terminal_buffers[node.id] = screen.append_line(message)
            self.terminal_streams[node.id] = self.terminal_streams.get(node.id, "") + message + "\n"
            return

        self.sessions[node.id] = runtime
        self.statuses[node.id] = "running"

    def drain_events(self) -> list[dict[str, str | int]]:
        events: list[dict[str, str | int]] = []

        try:
            while True:
                event = self.event_queue.get_nowait()
                if not isinstance(event, SessionEvent):
                    continue

                if event.kind == "output":
                    self.apply_output(event.session_id, str(event.payload))
                elif event.kind == "exit":
                    self.apply_exit(event.session_id, int(event.payload))

                events.append(
                    {
                        "kind": event.kind,
                        "session_id": event.session_id,
                        "payload": event.payload,
                    }
                )
        except queue.Empty:
            pass

        return events

    def session_stream(self, session_id: str | None) -> str:
        self.drain_events()
        return self.terminal_streams.get(session_id or "", "")

    def session_snapshot(self, session_id: str | None) -> str:
        self.drain_events()
        return self.terminal_buffers.get(session_id or "", "")

    def ui_state(self) -> dict[str, object]:
        self.drain_events()
        return {
            "selected_session_id": self.selected_session_id,
            "next_shell_number": self.next_shell_number,
            "tree": self._serialize_branch(None),
        }

    def _serialize_branch(self, parent_id: str | None) -> list[dict[str, object]]:
        serialized: list[dict[str, object]] = []
        for node in self.child_nodes(parent_id):
            serialized.append(
                {
                    "id": node.id,
                    "parent_id": node.parent_id,
                    "title": node.title,
                    "status": self.statuses.get(node.id, "idle"),
                    "is_collapsed": node.is_collapsed,
                    "initial_cwd": node.initial_cwd,
                    "children": self._serialize_branch(node.id),
                }
            )
        return serialized

    def _normalize_order(self, parent_id: str | None) -> None:
        for index, node in enumerate(self.child_nodes(parent_id)):
            node.order_index = index
            node.updated_at = utc_now()

    def _descendant_ids(self, session_id: str) -> list[str]:
        descendants: list[str] = []
        for child in self.child_nodes(session_id):
            descendants.append(child.id)
            descendants.extend(self._descendant_ids(child.id))
        return descendants

    def _move_to_parent(self, session_id: str, new_parent_id: str | None, insert_index: int) -> bool:
        node = self.node_by_id(session_id)
        if node is None:
            return False

        if new_parent_id == session_id or self._is_descendant(new_parent_id, session_id):
            return False

        old_parent_id = node.parent_id
        old_siblings = self.child_nodes(old_parent_id)
        moving_within_same_parent = old_parent_id == new_parent_id

        old_index = next((index for index, item in enumerate(old_siblings) if item.id == session_id), None)
        if old_index is None:
            return False

        if moving_within_same_parent:
            max_index = max(0, len(old_siblings) - 1)
            target_index = max(0, min(insert_index, max_index))
            if target_index == old_index:
                return False

            reordered = old_siblings[:]
            moving_node = reordered.pop(old_index)
            reordered.insert(target_index, moving_node)
            for index, sibling in enumerate(reordered):
                sibling.order_index = index
                sibling.updated_at = utc_now()
            self.persist()
            return True

        node.parent_id = new_parent_id
        node.updated_at = utc_now()

        if new_parent_id is not None:
            new_parent = self.node_by_id(new_parent_id)
            if new_parent is not None:
                new_parent.is_collapsed = False
                new_parent.updated_at = utc_now()

        self._normalize_order(old_parent_id)

        new_siblings = self.child_nodes(new_parent_id)
        target_index = max(0, min(insert_index, len(new_siblings)))
        reordered = [sibling for sibling in new_siblings if sibling.id != session_id]
        reordered.insert(target_index, node)
        for index, sibling in enumerate(reordered):
            sibling.order_index = index
            sibling.updated_at = utc_now()

        self.persist()
        return True

    def _is_descendant(self, session_id: str | None, ancestor_id: str) -> bool:
        current = self.node_by_id(session_id)
        while current is not None and current.parent_id is not None:
            if current.parent_id == ancestor_id:
                return True
            current = self.node_by_id(current.parent_id)
        return False

    def _close_runtime_async(self, session: PTYSession | None) -> None:
        if session is None:
            return
        threading.Thread(target=session.close, daemon=True).start()

    def _update_last_known_cwd(self, session_id: str, chunk: str) -> None:
        matches = self._osc7_pattern.findall(chunk)
        if not matches:
            return

        node = self.node_by_id(session_id)
        if node is None:
            return

        location = matches[-1]
        parsed = urlparse(location)
        if parsed.scheme != "file" or not parsed.path:
            return

        cwd = unquote(parsed.path)
        if cwd == node.last_known_cwd:
            return

        node.last_known_cwd = cwd
        node.updated_at = utc_now()
        self.persist()
