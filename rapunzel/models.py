from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class SessionNode:
    id: str
    parent_id: str | None
    title: str
    order_index: int
    is_collapsed: bool
    initial_cwd: str
    last_known_cwd: str | None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def from_dict(cls, payload: dict) -> "SessionNode":
        return cls(
            id=payload["id"],
            parent_id=payload.get("parent_id"),
            title=payload["title"],
            order_index=payload["order_index"],
            is_collapsed=payload.get("is_collapsed", False),
            initial_cwd=payload["initial_cwd"],
            last_known_cwd=payload.get("last_known_cwd"),
            created_at=payload.get("created_at", utc_now()),
            updated_at=payload.get("updated_at", utc_now()),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "title": self.title,
            "order_index": self.order_index,
            "is_collapsed": self.is_collapsed,
            "initial_cwd": self.initial_cwd,
            "last_known_cwd": self.last_known_cwd,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(slots=True)
class WorkspaceSnapshot:
    nodes: list[SessionNode]
    selected_session_id: str | None
    next_shell_number: int

    @classmethod
    def empty(cls) -> "WorkspaceSnapshot":
        return cls(nodes=[], selected_session_id=None, next_shell_number=1)

    @classmethod
    def from_dict(cls, payload: dict) -> "WorkspaceSnapshot":
        return cls(
            nodes=[SessionNode.from_dict(node) for node in payload.get("nodes", [])],
            selected_session_id=payload.get("selected_session_id"),
            next_shell_number=payload.get("next_shell_number", 1),
        )

    def to_dict(self) -> dict:
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "selected_session_id": self.selected_session_id,
            "next_shell_number": self.next_shell_number,
        }
