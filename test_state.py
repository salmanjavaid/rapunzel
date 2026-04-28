import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rapunzel.models import WorkspaceSnapshot
from rapunzel.state import MAX_TRANSCRIPT_CHARS, AppState
from rapunzel.store import WorkspaceStore


def _make_state(tmp_dir=None):
    """Create an AppState with a temp store and mocked PTY runtime."""
    if tmp_dir is None:
        tmp_dir = tempfile.mkdtemp()
    store = WorkspaceStore(path=Path(tmp_dir) / "ws.json")
    pushed_output = []
    pushed_exits = []
    st = AppState(
        store,
        push_output=lambda sid, data, sequence: pushed_output.append((sid, data, sequence)),
        push_exit=lambda sid, code, sequence: pushed_exits.append((sid, code, sequence)),
    )
    st._pushed_output = pushed_output
    st._pushed_exits = pushed_exits
    return st


@patch("rapunzel.state.PTYSession")
class CreateSessionTest(unittest.TestCase):
    def test_create_root_adds_node_and_selects_it(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        sid = st.create_root_session()

        self.assertEqual(len(st.tree), 1)
        self.assertEqual(st.tree[0].id, sid)
        self.assertIsNone(st.tree[0].parent_id)
        self.assertEqual(st.selected_session_id, sid)
        self.assertEqual(st.statuses[sid], "running")

    def test_create_child_under_parent(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        root_id = st.create_root_session()
        child_id = st.create_child_session()

        self.assertEqual(len(st.tree), 2)
        child = st.node_by_id(child_id)
        self.assertEqual(child.parent_id, root_id)
        self.assertEqual(st.selected_session_id, child_id)

    def test_create_child_expands_collapsed_parent(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        root_id = st.create_root_session()
        st.set_collapsed(root_id, True)
        self.assertTrue(st.node_by_id(root_id).is_collapsed)

        st.create_child_session()
        self.assertFalse(st.node_by_id(root_id).is_collapsed)

    def test_create_child_returns_none_when_no_selection(self, MockPTY):
        st = _make_state()
        result = st.create_child_session()
        self.assertIsNone(result)

    def test_create_child_under_returns_none_for_missing_parent(self, MockPTY):
        st = _make_state()
        result = st.create_child_session_under("nonexistent")
        self.assertIsNone(result)

    def test_shell_number_increments(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        st.create_root_session()
        st.create_root_session()
        self.assertEqual(st.next_shell_number, 3)
        self.assertEqual(st.tree[0].title, "Shell 1")
        self.assertEqual(st.tree[1].title, "Shell 2")


@patch("rapunzel.state.PTYSession")
class SelectAndRenameTest(unittest.TestCase):
    def test_select_changes_selected_id(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        s1 = st.create_root_session()
        s2 = st.create_root_session()

        st.select(s1)
        self.assertEqual(st.selected_session_id, s1)

    def test_rename_updates_title(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        sid = st.create_root_session()
        st.rename(sid, "  My Shell  ")
        self.assertEqual(st.node_by_id(sid).title, "My Shell")

    def test_rename_ignores_empty_string(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        sid = st.create_root_session()
        original = st.node_by_id(sid).title
        st.rename(sid, "   ")
        self.assertEqual(st.node_by_id(sid).title, original)

    def test_rename_nonexistent_is_noop(self, MockPTY):
        st = _make_state()
        st.rename("missing", "New")  # should not raise


@patch("rapunzel.state.PTYSession")
class CollapseTest(unittest.TestCase):
    def test_set_collapsed_toggles_flag(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        sid = st.create_root_session()
        self.assertFalse(st.node_by_id(sid).is_collapsed)

        st.set_collapsed(sid, True)
        self.assertTrue(st.node_by_id(sid).is_collapsed)

        st.set_collapsed(sid, False)
        self.assertFalse(st.node_by_id(sid).is_collapsed)


@patch("rapunzel.state.PTYSession")
class MoveTest(unittest.TestCase):
    def test_move_up_and_down(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        s1 = st.create_root_session()
        s2 = st.create_root_session()
        s3 = st.create_root_session()

        # s1=0, s2=1, s3=2
        st.move(s3, "up")
        siblings = st.child_nodes(None)
        ids = [n.id for n in siblings]
        self.assertEqual(ids, [s1, s3, s2])

        st.move(s1, "down")
        siblings = st.child_nodes(None)
        ids = [n.id for n in siblings]
        self.assertEqual(ids, [s3, s1, s2])

    def test_move_at_boundary_is_noop(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        s1 = st.create_root_session()
        s2 = st.create_root_session()

        st.move(s1, "up")  # already first
        siblings = st.child_nodes(None)
        self.assertEqual([n.id for n in siblings], [s1, s2])

        st.move(s2, "down")  # already last
        siblings = st.child_nodes(None)
        self.assertEqual([n.id for n in siblings], [s1, s2])


@patch("rapunzel.state.PTYSession")
class CloseTest(unittest.TestCase):
    def test_close_removes_node_and_reparents_children(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        MockPTY.return_value.close.return_value = None
        st = _make_state()
        root = st.create_root_session()
        child = st.create_child_session()

        st.select(root)
        st.close(root)

        self.assertIsNone(st.node_by_id(root))
        child_node = st.node_by_id(child)
        self.assertIsNotNone(child_node)
        self.assertIsNone(child_node.parent_id)  # reparented to root level

    def test_close_selects_another_node(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        MockPTY.return_value.close.return_value = None
        st = _make_state()
        s1 = st.create_root_session()
        s2 = st.create_root_session()

        st.select(s1)
        st.close(s1)
        self.assertEqual(st.selected_session_id, s2)

    def test_close_last_node_clears_selection(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        MockPTY.return_value.close.return_value = None
        st = _make_state()
        sid = st.create_root_session()
        st.close(sid)
        self.assertIsNone(st.selected_session_id)
        self.assertEqual(len(st.tree), 0)

    def test_close_branch_removes_subtree(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        MockPTY.return_value.close.return_value = None
        st = _make_state()
        root = st.create_root_session()
        st.select(root)
        child = st.create_child_session()

        st.close_branch(root)
        self.assertEqual(len(st.tree), 0)
        self.assertIsNone(st.selected_session_id)

    def test_close_cleans_up_terminal_state(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        MockPTY.return_value.close.return_value = None
        st = _make_state()
        sid = st.create_root_session()
        st.close(sid)

        self.assertNotIn(sid, st.terminal_buffers)
        self.assertNotIn(sid, st.terminal_streams)
        self.assertNotIn(sid, st.terminal_screens)
        self.assertNotIn(sid, st.statuses)


@patch("rapunzel.state.PTYSession")
class MoveRelativeTest(unittest.TestCase):
    def test_move_as_child_of_target(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        s1 = st.create_root_session()
        s2 = st.create_root_session()

        result = st.move_relative_to_target(s2, s1, "child")
        self.assertTrue(result)
        self.assertEqual(st.node_by_id(s2).parent_id, s1)

    def test_move_as_sibling_of_target(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        s1 = st.create_root_session()
        s2 = st.create_root_session()
        s3 = st.create_root_session()

        # Move s3 as sibling after s1 (should end up at index 1)
        result = st.move_relative_to_target(s3, s1, "sibling")
        self.assertTrue(result)
        siblings = st.child_nodes(None)
        ids = [n.id for n in siblings]
        self.assertEqual(ids, [s1, s3, s2])

    def test_move_to_root(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        root = st.create_root_session()
        st.select(root)
        child = st.create_child_session()

        result = st.move_relative_to_target(child, None, "root")
        self.assertTrue(result)
        self.assertIsNone(st.node_by_id(child).parent_id)

    def test_cannot_move_node_into_own_descendant(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        root = st.create_root_session()
        st.select(root)
        child = st.create_child_session()

        result = st.move_relative_to_target(root, child, "child")
        self.assertFalse(result)

    def test_cannot_move_node_to_itself(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        s1 = st.create_root_session()
        result = st.move_relative_to_target(s1, s1, "child")
        self.assertFalse(result)


@patch("rapunzel.state.PTYSession")
class OutputAndEventsTest(unittest.TestCase):
    def test_apply_output_updates_buffers_and_status(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        sid = st.create_root_session()

        st.apply_output(sid, "hello world")
        self.assertIn("hello world", st.terminal_buffers[sid])
        self.assertIn("hello world", st.terminal_streams[sid])
        self.assertEqual(st.statuses[sid], "running")

    def test_apply_exit_updates_status(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        sid = st.create_root_session()

        st.apply_exit(sid, 0)
        self.assertEqual(st.statuses[sid], "exited 0")
        self.assertIn("exited with code 0", st.terminal_buffers[sid])

    def test_drain_events_processes_queued_output(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        sid = st.create_root_session()

        from rapunzel.state import SessionEvent
        st.event_queue.put(SessionEvent("output", sid, "data chunk"))
        events = st.drain_events()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "output")
        self.assertIn("data chunk", st.terminal_streams[sid])

    def test_session_snapshot_drains_events_first(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        sid = st.create_root_session()

        from rapunzel.state import SessionEvent
        st.event_queue.put(SessionEvent("output", sid, "pending"))
        snapshot = st.session_snapshot(sid)
        self.assertIn("pending", snapshot)

    def test_session_snapshot_payload_includes_applied_sequence(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        sid = st.create_root_session()

        from rapunzel.state import SessionEvent
        st.event_queue.put(SessionEvent("output", sid, "pending", 42))
        snapshot = st.session_snapshot_payload(sid)

        self.assertIn("pending", snapshot["text"])
        self.assertEqual(snapshot["sequence"], 42)

    def test_drain_events_batches_output_before_rendering_snapshot(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        sid = st.create_root_session()

        from rapunzel.state import SessionEvent
        st.event_queue.put(SessionEvent("output", sid, "hello ", 10))
        st.event_queue.put(SessionEvent("output", sid, "world", 11))
        events = st.drain_events()

        self.assertEqual(len(events), 2)
        self.assertIn("hello world", st.terminal_buffers[sid])
        self.assertEqual(st.applied_sequences[sid], 11)

    def test_terminal_stream_is_bounded_for_long_running_output(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        sid = st.create_root_session()
        st.terminal_streams[sid] = "a" * (MAX_TRANSCRIPT_CHARS - 5)

        st._append_terminal_stream(sid, "b" * 10)

        self.assertEqual(len(st.terminal_streams[sid]), MAX_TRANSCRIPT_CHARS)
        self.assertTrue(st.terminal_streams[sid].endswith("b" * 10))


@patch("rapunzel.state.PTYSession")
class UIStateTest(unittest.TestCase):
    def test_ui_state_returns_nested_tree(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        root = st.create_root_session()
        st.select(root)
        child = st.create_child_session()

        ui = st.ui_state()
        self.assertEqual(ui["selected_session_id"], child)
        self.assertEqual(len(ui["tree"]), 1)  # one root
        self.assertEqual(ui["tree"][0]["id"], root)
        self.assertEqual(len(ui["tree"][0]["children"]), 1)
        self.assertEqual(ui["tree"][0]["children"][0]["id"], child)

    def test_ui_state_includes_status(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        sid = st.create_root_session()
        ui = st.ui_state()
        self.assertEqual(ui["tree"][0]["status"], "running")


@patch("rapunzel.state.PTYSession")
class CwdTrackingTest(unittest.TestCase):
    def test_osc7_updates_last_known_cwd(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        sid = st.create_root_session()
        node = st.node_by_id(sid)
        original_cwd = node.last_known_cwd

        osc7 = "\x1b]7;file:///Users/test/project\x07"
        st.apply_output(sid, osc7)

        self.assertEqual(node.last_known_cwd, "/Users/test/project")

    def test_osc7_with_st_terminator(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        sid = st.create_root_session()
        node = st.node_by_id(sid)

        osc7 = "\x1b]7;file:///home/user/dir\x1b\\"
        st.apply_output(sid, osc7)

        self.assertEqual(node.last_known_cwd, "/home/user/dir")

    def test_child_inherits_parent_cwd(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        root_id = st.create_root_session()
        root_node = st.node_by_id(root_id)

        osc7 = "\x1b]7;file:///Users/test/work\x07"
        st.apply_output(root_id, osc7)

        child_id = st.create_child_session()
        child_node = st.node_by_id(child_id)
        self.assertEqual(child_node.initial_cwd, "/Users/test/work")


@patch("rapunzel.state.PTYSession")
class PersistenceTest(unittest.TestCase):
    def test_create_and_close_persist_to_store(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        MockPTY.return_value.close.return_value = None
        with tempfile.TemporaryDirectory() as tmp:
            st = _make_state(tmp)
            sid = st.create_root_session()

            loaded = st.store.load()
            self.assertEqual(len(loaded.nodes), 1)
            self.assertEqual(loaded.selected_session_id, sid)

            st.close(sid)
            loaded = st.store.load()
            self.assertEqual(len(loaded.nodes), 0)

    def test_rename_persists(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        with tempfile.TemporaryDirectory() as tmp:
            st = _make_state(tmp)
            sid = st.create_root_session()
            st.rename(sid, "Custom Name")

            loaded = st.store.load()
            self.assertEqual(loaded.nodes[0].title, "Custom Name")


@patch("rapunzel.state.PTYSession")
class StartRuntimeFailureTest(unittest.TestCase):
    def test_failed_start_sets_error_status(self, MockPTY):
        MockPTY.return_value.start.side_effect = OSError("no shell")
        st = _make_state()
        sid = st.create_root_session()

        self.assertEqual(st.statuses[sid], "error")
        self.assertIn("failed to start shell", st.terminal_buffers[sid])
        self.assertNotIn(sid, st.sessions)


@patch("rapunzel.state.PTYSession")
class ResizeTest(unittest.TestCase):
    def test_resize_session_updates_screen_and_pty(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        sid = st.create_root_session()

        st.resize_session(sid, 50, 100)
        screen = st.terminal_screens[sid]
        self.assertEqual(screen.rows, 50)
        self.assertEqual(screen.cols, 100)
        MockPTY.return_value.resize.assert_called_with(50, 100)

    def test_resize_selected_session(self, MockPTY):
        MockPTY.return_value.start.return_value = None
        st = _make_state()
        sid = st.create_root_session()
        st.resize_selected_session(24, 80)
        MockPTY.return_value.resize.assert_called_with(24, 80)

    def test_resize_with_no_selection_is_noop(self, MockPTY):
        st = _make_state()
        st.resize_selected_session(24, 80)  # should not raise


if __name__ == "__main__":
    unittest.main()
