from __future__ import annotations

import os
import queue
import uuid
from dataclasses import dataclass
from typing import Literal

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
    def __init__(self, store: WorkspaceStore) -> None:
        self.store = store
        self.tree: list[SessionNode] = []
        self.selected_session_id: str | None = None
        self.terminal_buffers: dict[str, str] = {}
        self.terminal_screens: dict[str, TerminalScreen] = {}
        self.statuses: dict[str, str] = {}
        self.sessions: dict[str, PTYSession] = {}
        self.event_queue: queue.Queue[SessionEvent] = queue.Queue()
        self.next_shell_number = 1

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

    def close(self, session_id: str) -> None:
        node = self.node_by_id(session_id)
        if node is None:
            return

        session = self.sessions.pop(session_id, None)
        if session is not None:
            session.close()

        children = self.child_nodes(node.id)
        self.tree = [item for item in self.tree if item.id != session_id]
        for child in children:
            child.parent_id = node.parent_id
            child.updated_at = utc_now()

        self._normalize_order(node.parent_id)
        self.terminal_buffers.pop(session_id, None)
        self.terminal_screens.pop(session_id, None)
        self.statuses.pop(session_id, None)

        if self.selected_session_id == session_id:
            self.selected_session_id = self.visible_nodes()[0].id if self.tree else None

        self.persist()

    def send_input_to_selected_session(self, data: bytes) -> None:
        if self.selected_session_id is None:
            return

        session = self.sessions.get(self.selected_session_id)
        if session is not None:
            session.send(data)

    def resize_selected_session(self, rows: int, cols: int) -> None:
        if self.selected_session_id is None:
            return

        session = self.sessions.get(self.selected_session_id)
        if session is not None:
            session.resize(rows, cols)

    def apply_output(self, session_id: str, chunk: str) -> str:
        screen = self.terminal_screens.setdefault(session_id, TerminalScreen())
        rendered = screen.feed(chunk)
        self.terminal_buffers[session_id] = rendered
        if session_id in self.statuses and self.statuses[session_id] != "error":
            self.statuses[session_id] = "running"
        return rendered

    def apply_exit(self, session_id: str, exit_code: int) -> str:
        message = f"\n[process exited with code {exit_code}]\n"
        screen = self.terminal_screens.setdefault(session_id, TerminalScreen())
        self.terminal_buffers[session_id] = screen.append_line(message.rstrip("\n"))
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
        runtime = PTYSession(
            session_id=node.id,
            cwd=node.last_known_cwd or node.initial_cwd,
            on_output=lambda session_id, chunk: self.event_queue.put(
                SessionEvent("output", session_id, chunk)
            ),
            on_exit=lambda session_id, code: self.event_queue.put(
                SessionEvent("exit", session_id, code)
            ),
        )

        try:
            runtime.start()
        except Exception as exc:
            self.statuses[node.id] = "error"
            screen = self.terminal_screens.setdefault(node.id, TerminalScreen())
            self.terminal_buffers[node.id] = screen.append_line(f"[failed to start shell: {exc}]")
            return

        self.sessions[node.id] = runtime
        self.statuses[node.id] = "running"

    def _normalize_order(self, parent_id: str | None) -> None:
        for index, node in enumerate(self.child_nodes(parent_id)):
            node.order_index = index
            node.updated_at = utc_now()
