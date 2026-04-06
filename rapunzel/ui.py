from __future__ import annotations

import queue
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from rapunzel.state import AppState, SessionEvent
from rapunzel.store import WorkspaceStore


class RapunzelUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Rapunzel")
        self.root.geometry("1320x820")
        self.root.minsize(980, 620)

        self.store = WorkspaceStore()
        self.state = AppState(self.store)

        self.active_title = tk.StringVar(value="No session selected")
        self.active_meta = tk.StringVar(value="Create a root session to begin.")
        self.branch_name = tk.StringVar(value="")
        self._resize_after_id: str | None = None

        self._configure_style()
        self._build_layout()
        self._bind_shortcuts()

        self.state.bootstrap()
        self._refresh_tree()
        self._refresh_terminal_view()
        self._refresh_actions()

        self.root.after(40, self._pump_events)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def run(self) -> None:
        self.root.mainloop()

    def _configure_style(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.root.configure(background="#f2efe8")
        style.configure("Treeview", rowheight=28, font=("Menlo", 11))
        style.configure("Treeview.Heading", font=("Helvetica", 11, "bold"))
        style.configure("Action.TButton", padding=(10, 7))
        style.configure("Primary.TButton", padding=(12, 8))

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        paned = ttk.Panedwindow(container, orient="horizontal")
        paned.pack(fill="both", expand=True)

        sidebar = ttk.Frame(paned, padding=(0, 0, 12, 0))
        detail = ttk.Frame(paned)
        paned.add(sidebar, weight=1)
        paned.add(detail, weight=3)

        self._build_sidebar(sidebar)
        self._build_detail(detail)

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill="x")

        title_frame = ttk.Frame(header)
        title_frame.pack(side="left", fill="x", expand=True)
        ttk.Label(title_frame, text="Rapunzel", font=("Helvetica", 10, "bold")).pack(anchor="w")
        ttk.Label(title_frame, text="Terminal Tree", font=("Helvetica", 18, "bold")).pack(anchor="w")

        actions = ttk.Frame(header)
        actions.pack(side="right", anchor="n")
        self.new_root_button = ttk.Button(
            actions,
            text="New Root",
            style="Primary.TButton",
            command=self._create_root,
        )
        self.new_root_button.pack(fill="x")
        self.new_child_button = ttk.Button(
            actions,
            text="New Child",
            style="Action.TButton",
            command=self._create_child,
        )
        self.new_child_button.pack(fill="x", pady=(8, 0))

        helper = tk.Label(
            parent,
            text="Cmd/Ctrl+T new root   Cmd/Ctrl+B new child   F2 rename   Cmd/Ctrl+W close",
            bg="#e6dfd0",
            justify="left",
            anchor="w",
            padx=12,
            pady=10,
            font=("Helvetica", 10),
        )
        helper.pack(fill="x", pady=(14, 12))

        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(0, 10))
        self.rename_button = ttk.Button(toolbar, text="Rename", command=self._rename_selected)
        self.rename_button.pack(side="left")
        self.move_up_button = ttk.Button(toolbar, text="Up", command=lambda: self._move_selected("up"))
        self.move_up_button.pack(side="left", padx=(8, 0))
        self.move_down_button = ttk.Button(toolbar, text="Down", command=lambda: self._move_selected("down"))
        self.move_down_button.pack(side="left", padx=(8, 0))
        self.close_button = ttk.Button(toolbar, text="Close", command=self._close_selected)
        self.close_button.pack(side="left", padx=(8, 0))

        rename_panel = ttk.Frame(parent)
        rename_panel.pack(fill="x", pady=(0, 10))
        ttk.Label(rename_panel, text="Branch Name", font=("Helvetica", 10, "bold")).pack(anchor="w")
        rename_row = ttk.Frame(rename_panel)
        rename_row.pack(fill="x", pady=(6, 0))
        self.rename_entry = ttk.Entry(rename_row, textvariable=self.branch_name)
        self.rename_entry.pack(side="left", fill="x", expand=True)
        self.rename_apply_button = ttk.Button(rename_row, text="Apply", command=self._apply_branch_name)
        self.rename_apply_button.pack(side="left", padx=(8, 0))
        self.rename_entry.bind("<Return>", self._apply_branch_name)

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True)

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical")
        tree_scroll.pack(side="right", fill="y")

        self.tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse", yscrollcommand=tree_scroll.set)
        self.tree.pack(fill="both", expand=True)
        tree_scroll.configure(command=self.tree.yview)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.tree.bind("<<TreeviewClose>>", self._on_tree_close)
        self.tree.bind("<Double-1>", lambda _event: self._rename_selected())

    def _build_detail(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill="x", pady=(0, 12))

        ttk.Label(header, text="Active Session", font=("Helvetica", 10, "bold")).pack(anchor="w")
        ttk.Label(header, textvariable=self.active_title, font=("Helvetica", 20, "bold")).pack(anchor="w", pady=(4, 2))
        ttk.Label(header, textvariable=self.active_meta, font=("Helvetica", 11)).pack(anchor="w")

        terminal_frame = ttk.Frame(parent)
        terminal_frame.pack(fill="both", expand=True)

        self.terminal_font = tkfont.Font(family="Menlo", size=12)
        self.terminal = tk.Text(
            terminal_frame,
            wrap="none",
            undo=False,
            bg="#111111",
            fg="#e7f6d5",
            insertbackground="#f7f2a1",
            insertwidth=0,
            relief="flat",
            padx=14,
            pady=14,
            font=self.terminal_font,
        )
        self.terminal.pack(side="left", fill="both", expand=True)

        y_scroll = ttk.Scrollbar(terminal_frame, orient="vertical", command=self.terminal.yview)
        y_scroll.pack(side="right", fill="y")
        x_scroll = ttk.Scrollbar(parent, orient="horizontal", command=self.terminal.xview)
        x_scroll.pack(fill="x")
        self.terminal.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.terminal.bind("<KeyPress>", self._on_terminal_keypress)
        self.terminal.bind("<Configure>", self._schedule_resize)
        self.terminal.bind("<Button-1>", lambda _event: self.terminal.focus_set())
        self.terminal.bind("<Command-v>", self._paste_to_terminal)
        self.terminal.bind("<Control-v>", self._paste_to_terminal)

    def _bind_shortcuts(self) -> None:
        for sequence in ("<Command-t>", "<Control-t>"):
            self.root.bind_all(sequence, lambda _event: self._create_root())
        for sequence in ("<Command-b>", "<Control-b>"):
            self.root.bind_all(sequence, lambda _event: self._create_child())
        for sequence in ("<Command-w>", "<Control-w>"):
            self.root.bind_all(sequence, lambda _event: self._close_selected())
        self.root.bind_all("<F2>", lambda _event: self._rename_selected())

    def _create_root(self) -> None:
        session_id = self.state.create_root_session()
        self._refresh_tree()
        self._focus_session(session_id)

    def _create_child(self) -> None:
        session_id = self.state.create_child_session()
        if session_id is None:
            return
        self._refresh_tree()
        self._focus_session(session_id)

    def _rename_selected(self) -> None:
        self.rename_entry.focus_set()
        self.rename_entry.selection_range(0, "end")

    def _apply_branch_name(self, _event: tk.Event | None = None) -> str | None:
        session_id = self.state.selected_session_id
        if session_id is None:
            return "break"

        self.state.rename(session_id, self.branch_name.get())
        node = self.state.node_by_id(session_id)
        if node is not None:
            self.branch_name.set(node.title)
        self._refresh_tree()
        self._refresh_header()
        return "break"

    def _move_selected(self, direction: str) -> None:
        session_id = self.state.selected_session_id
        if session_id is None:
            return

        self.state.move(session_id, direction)
        self._refresh_tree()
        self._focus_session(session_id)

    def _close_selected(self) -> None:
        session_id = self.state.selected_session_id
        if session_id is None:
            return

        self.state.close(session_id)
        self._refresh_tree()
        self._refresh_terminal_view()
        self._refresh_actions()

    def _refresh_tree(self) -> None:
        selected = self.state.selected_session_id
        self.tree.delete(*self.tree.get_children())
        self._insert_branch("", None)

        if selected and self.tree.exists(selected):
            self.tree.selection_set(selected)
            self.tree.focus(selected)

        self._refresh_actions()
        self._refresh_header()

    def _insert_branch(self, parent_item: str, parent_id: str | None) -> None:
        for node in self.state.child_nodes(parent_id):
            label = f"{node.title} [{self.state.statuses.get(node.id, 'idle')}]"
            self.tree.insert(parent_item, "end", iid=node.id, text=label, open=not node.is_collapsed)
            self._insert_branch(node.id, node.id)

    def _focus_session(self, session_id: str) -> None:
        if self.tree.exists(session_id):
            self.tree.selection_set(session_id)
            self.tree.focus(session_id)
            self.tree.see(session_id)
        self.state.select(session_id)
        self._refresh_terminal_view()
        self._schedule_resize()

    def _refresh_header(self) -> None:
        node = self.state.node_by_id(self.state.selected_session_id)
        if node is None:
            self.active_title.set("No session selected")
            self.active_meta.set("Create a root session to begin.")
            if self.root.focus_get() != self.rename_entry:
                self.branch_name.set("")
            return

        status = self.state.statuses.get(node.id, "idle")
        self.active_title.set(node.title)
        self.active_meta.set(f"Status: {status}   Initial cwd: {node.initial_cwd}")
        if self.root.focus_get() != self.rename_entry:
            self.branch_name.set(node.title)

    def _refresh_terminal_view(self) -> None:
        session_id = self.state.selected_session_id
        buffer = self.state.terminal_buffers.get(session_id or "", "")
        self.terminal.delete("1.0", "end")
        if buffer:
            self.terminal.insert("end", buffer)
        self.terminal.see("end")
        self._refresh_header()
        self._refresh_actions()

    def _refresh_actions(self) -> None:
        has_selection = self.state.selected_session_id is not None
        child_state = "normal" if has_selection else "disabled"
        action_state = "normal" if has_selection else "disabled"
        self.new_child_button.configure(state=child_state)
        self.rename_button.configure(state=action_state)
        self.rename_entry.configure(state=action_state)
        self.rename_apply_button.configure(state=action_state)
        self.move_up_button.configure(state=action_state)
        self.move_down_button.configure(state=action_state)
        self.close_button.configure(state=action_state)

    def _on_tree_select(self, _event: tk.Event) -> None:
        selection = self.tree.selection()
        session_id = selection[0] if selection else None
        self.state.select(session_id)
        self._refresh_terminal_view()
        self._schedule_resize()

    def _on_tree_open(self, _event: tk.Event) -> None:
        session_id = self.tree.focus()
        if session_id:
            self.state.set_collapsed(session_id, False)

    def _on_tree_close(self, _event: tk.Event) -> None:
        session_id = self.tree.focus()
        if session_id:
            self.state.set_collapsed(session_id, True)

    def _pump_events(self) -> None:
        needs_tree_refresh = False
        refresh_selected = False

        try:
            while True:
                event = self.state.event_queue.get_nowait()
                if not isinstance(event, SessionEvent):
                    continue

                if event.kind == "output":
                    self.state.apply_output(event.session_id, str(event.payload))
                    if event.session_id == self.state.selected_session_id:
                        refresh_selected = True
                elif event.kind == "exit":
                    self.state.apply_exit(event.session_id, int(event.payload))
                    if event.session_id == self.state.selected_session_id:
                        refresh_selected = True
                    needs_tree_refresh = True
        except queue.Empty:
            pass

        if refresh_selected:
            self._refresh_terminal_view()
        if needs_tree_refresh:
            self._refresh_tree()

        self.root.after(40, self._pump_events)

    def _schedule_resize(self, _event: tk.Event | None = None) -> None:
        if self._resize_after_id is not None:
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(80, self._resize_selected_session)

    def _resize_selected_session(self) -> None:
        self._resize_after_id = None
        char_width = max(self.terminal_font.measure("M"), 1)
        line_height = max(self.terminal_font.metrics("linespace"), 1)
        cols = max((self.terminal.winfo_width() - 28) // char_width, 20)
        rows = max((self.terminal.winfo_height() - 28) // line_height, 8)
        self.state.resize_selected_session(rows, cols)

    def _on_terminal_keypress(self, event: tk.Event) -> str:
        data = self._translate_keypress(event)
        if data is not None:
            self.state.send_input_to_selected_session(data)
        return "break"

    def _paste_to_terminal(self, _event: tk.Event) -> str:
        try:
            clipboard = self.root.clipboard_get()
        except tk.TclError:
            return "break"

        if clipboard:
            self.state.send_input_to_selected_session(clipboard.encode("utf-8"))
        return "break"

    def _translate_keypress(self, event: tk.Event) -> bytes | None:
        control_pressed = bool(event.state & 0x4)
        special = {
            "Return": b"\r",
            "BackSpace": b"\x7f",
            "Tab": b"\t",
            "Escape": b"\x1b",
            "Up": b"\x1b[A",
            "Down": b"\x1b[B",
            "Right": b"\x1b[C",
            "Left": b"\x1b[D",
            "Home": b"\x1b[H",
            "End": b"\x1b[F",
        }

        if event.keysym in {"Delete", "KP_Delete"}:
            if event.char in {"\x08", "\x7f"}:
                return b"\x7f"
            return b"\x1b[3~"

        if event.keysym in special:
            return special[event.keysym]

        if control_pressed and len(event.keysym) == 1:
            char = event.keysym.upper()
            if "A" <= char <= "Z":
                return bytes([ord(char) - 64])

        if event.char:
            return event.char.encode("utf-8")

        return None

    def _on_close(self) -> None:
        self.state.shutdown()
        self.root.destroy()


def main() -> None:
    RapunzelUI().run()
