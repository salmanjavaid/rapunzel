import json
import tempfile
import unittest
from pathlib import Path

from rapunzel.models import SessionNode, WorkspaceSnapshot
from rapunzel.store import WorkspaceStore


class WorkspaceStoreTest(unittest.TestCase):
    def test_load_returns_empty_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WorkspaceStore(path=Path(tmp) / "missing.json")
            snap = store.load()
            self.assertEqual(snap.nodes, [])
            self.assertIsNone(snap.selected_session_id)

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace.json"
            store = WorkspaceStore(path=path)

            node = SessionNode(
                id="s1", parent_id=None, title="Root",
                order_index=0, is_collapsed=False,
                initial_cwd="/tmp", last_known_cwd="/tmp",
            )
            snap = WorkspaceSnapshot(nodes=[node], selected_session_id="s1", next_shell_number=2)
            store.save(snap)

            self.assertTrue(path.exists())
            loaded = store.load()
            self.assertEqual(len(loaded.nodes), 1)
            self.assertEqual(loaded.nodes[0].id, "s1")
            self.assertEqual(loaded.selected_session_id, "s1")
            self.assertEqual(loaded.next_shell_number, 2)

    def test_save_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "deep" / "workspace.json"
            store = WorkspaceStore(path=path)
            store.save(WorkspaceSnapshot.empty())
            self.assertTrue(path.exists())

    def test_save_produces_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace.json"
            store = WorkspaceStore(path=path)
            store.save(WorkspaceSnapshot.empty())

            raw = path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            self.assertIn("nodes", parsed)
            self.assertIn("selected_session_id", parsed)


if __name__ == "__main__":
    unittest.main()
