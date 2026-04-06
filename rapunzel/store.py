from __future__ import annotations

import json
import os
from pathlib import Path

from rapunzel.models import WorkspaceSnapshot


class WorkspaceStore:
    def __init__(self, path: Path | None = None) -> None:
        env_override = os.environ.get("RAPUNZEL_WORKSPACE_PATH")
        if path is not None:
            self.path = path
        elif env_override:
            self.path = Path(env_override).expanduser()
        else:
            self.path = self.default_path()

    @staticmethod
    def default_path() -> Path:
        return Path.home() / ".rapunzel" / "workspace.json"

    def load(self) -> WorkspaceSnapshot:
        if not self.path.exists():
            return WorkspaceSnapshot.empty()

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return WorkspaceSnapshot.from_dict(payload)

    def save(self, snapshot: WorkspaceSnapshot) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(snapshot.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
