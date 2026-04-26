import unittest

from rapunzel.models import SessionNode, WorkspaceSnapshot, utc_now


class SessionNodeTest(unittest.TestCase):
    def _make_node(self, **overrides):
        defaults = {
            "id": "abc-123",
            "parent_id": None,
            "title": "Shell 1",
            "order_index": 0,
            "is_collapsed": False,
            "initial_cwd": "/tmp",
            "last_known_cwd": "/tmp/sub",
            "created_at": "2025-01-01T00:00:00+00:00",
            "updated_at": "2025-01-01T00:00:00+00:00",
        }
        defaults.update(overrides)
        return SessionNode(**defaults)

    def test_roundtrip_to_dict_and_back(self):
        node = self._make_node()
        restored = SessionNode.from_dict(node.to_dict())
        self.assertEqual(restored.id, node.id)
        self.assertEqual(restored.parent_id, node.parent_id)
        self.assertEqual(restored.title, node.title)
        self.assertEqual(restored.order_index, node.order_index)
        self.assertEqual(restored.is_collapsed, node.is_collapsed)
        self.assertEqual(restored.initial_cwd, node.initial_cwd)
        self.assertEqual(restored.last_known_cwd, node.last_known_cwd)

    def test_from_dict_defaults_missing_optional_fields(self):
        minimal = {
            "id": "x",
            "title": "T",
            "order_index": 0,
            "initial_cwd": "/",
        }
        node = SessionNode.from_dict(minimal)
        self.assertIsNone(node.parent_id)
        self.assertFalse(node.is_collapsed)
        self.assertIsNone(node.last_known_cwd)
        self.assertIsNotNone(node.created_at)
        self.assertIsNotNone(node.updated_at)

    def test_to_dict_includes_all_fields(self):
        node = self._make_node(parent_id="parent-1", is_collapsed=True)
        d = node.to_dict()
        self.assertEqual(d["id"], "abc-123")
        self.assertEqual(d["parent_id"], "parent-1")
        self.assertTrue(d["is_collapsed"])
        self.assertIn("created_at", d)
        self.assertIn("updated_at", d)


class WorkspaceSnapshotTest(unittest.TestCase):
    def test_empty_snapshot(self):
        snap = WorkspaceSnapshot.empty()
        self.assertEqual(snap.nodes, [])
        self.assertIsNone(snap.selected_session_id)
        self.assertEqual(snap.next_shell_number, 1)

    def test_roundtrip_to_dict_and_back(self):
        node = SessionNode(
            id="n1", parent_id=None, title="Root",
            order_index=0, is_collapsed=False,
            initial_cwd="/home", last_known_cwd="/home/sub",
        )
        snap = WorkspaceSnapshot(nodes=[node], selected_session_id="n1", next_shell_number=2)
        restored = WorkspaceSnapshot.from_dict(snap.to_dict())
        self.assertEqual(len(restored.nodes), 1)
        self.assertEqual(restored.nodes[0].id, "n1")
        self.assertEqual(restored.selected_session_id, "n1")
        self.assertEqual(restored.next_shell_number, 2)

    def test_from_dict_defaults(self):
        snap = WorkspaceSnapshot.from_dict({})
        self.assertEqual(snap.nodes, [])
        self.assertIsNone(snap.selected_session_id)
        self.assertEqual(snap.next_shell_number, 1)


class UtcNowTest(unittest.TestCase):
    def test_returns_iso_string_with_timezone(self):
        ts = utc_now()
        self.assertIn("+00:00", ts)


if __name__ == "__main__":
    unittest.main()
