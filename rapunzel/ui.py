from __future__ import annotations

import queue
import platform
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import simpledialog
from tkinter import ttk

from rapunzel.state import AppState, SessionEvent
from rapunzel.store import WorkspaceStore


PALETTE = {
    "window": "#dfe6ef",
    "surface": "#f8fafc",
    "surface_alt": "#eef3f9",
    "surface_edge": "#c8d2df",
    "text": "#18212f",
    "muted": "#64748b",
    "accent": "#4f7cff",
    "accent_hover": "#3c68f0",
    "accent_soft": "#e6eeff",
    "terminal": "#111827",
    "terminal_edge": "#263244",
    "terminal_text": "#e8eef9",
    "terminal_cursor": "#f7c96b",
}

NEW_ROOT_ROW_ID = "__new_root__"


class RoundedCard(tk.Canvas):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        bg_color: str,
        radius: int = 24,
        padding: int | tuple[int, int, int, int] = 18,
        border_color: str | None = None,
        border_width: int = 1,
        **kwargs: object,
    ) -> None:
        super().__init__(
            parent,
            bg=parent.cget("bg"),
            highlightthickness=0,
            bd=0,
            relief="flat",
            **kwargs,
        )
        self.bg_color = bg_color
        self.radius = radius
        self.border_color = border_color or bg_color
        self.border_width = border_width
        self.padding = self._normalize_padding(padding)

        self.inner = tk.Frame(self, bg=bg_color, bd=0, highlightthickness=0)
        self._window_id = self.create_window(0, 0, anchor="nw", window=self.inner)
        self.bind("<Configure>", self._redraw)

    def _normalize_padding(self, padding: int | tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        if isinstance(padding, int):
            return (padding, padding, padding, padding)
        return padding

    def _redraw(self, _event: tk.Event | None = None) -> None:
        self.delete("card")

        width = max(self.winfo_width(), 2)
        height = max(self.winfo_height(), 2)
        left, top, right, bottom = self.padding

        self._draw_round_rect(
            self.border_width,
            self.border_width,
            width - self.border_width,
            height - self.border_width,
            radius=min(self.radius, width // 2, height // 2),
            fill=self.bg_color,
            outline=self.border_color,
            width=self.border_width,
        )
        self.coords(self._window_id, left, top)
        self.itemconfigure(
            self._window_id,
            width=max(1, width - left - right),
            height=max(1, height - top - bottom),
        )

    def _draw_round_rect(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        *,
        radius: int,
        fill: str,
        outline: str,
        width: int,
    ) -> None:
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        self.create_polygon(
            points,
            smooth=True,
            splinesteps=36,
            fill=fill,
            outline=outline,
            width=width,
            tags="card",
        )


class AutoScrollbar(ttk.Scrollbar):
    def set(self, first: str, last: str) -> None:
        start = float(first)
        end = float(last)
        if start <= 0.0 and end >= 1.0:
            self.grid_remove()
        else:
            self.grid()
        super().set(first, last)


class RapunzelUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Rapunzel")
        self.root.geometry("1360x860")
        self.root.minsize(1040, 680)
        self.root.configure(background=PALETTE["window"])
        self._icon_image: tk.PhotoImage | None = None
        self._set_app_icon()

        self.store = WorkspaceStore()
        self.state = AppState(self.store)

        self.active_title = tk.StringVar(value="No session selected")
        self.active_meta = tk.StringVar(value="Create a root session to begin.")
        self._resize_after_id: str | None = None
        self._drag_session_id: str | None = None
        self._drag_target_id: str | None = None
        self._drag_drop_mode = "sibling"
        self._drag_start_xy: tuple[int, int] | None = None
        self._drag_active = False
        self._context_target_id: str | None = None
        self._displayed_session_id: str | None = None
        self._displayed_buffer: str | None = None

        self._configure_style()
        self._build_layout()
        self._bind_shortcuts()

        self.state.bootstrap()
        self._refresh_tree()
        self._refresh_terminal_view()
        self._refresh_actions()

        self.root.after(40, self._pump_events)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_app_icon(self) -> None:
        icon_path = Path(__file__).resolve().parent.parent / "icon.png"
        if not icon_path.exists():
            return

        try:
            self._icon_image = tk.PhotoImage(file=str(icon_path))
            self.root.iconphoto(True, self._icon_image)
        except tk.TclError:
            self._icon_image = None

        if platform.system() != "Darwin":
            return

        try:
            import AppKit

            image = AppKit.NSImage.alloc().initWithContentsOfFile_(str(icon_path))
            if image is not None:
                AppKit.NSApplication.sharedApplication().setApplicationIconImage_(image)
        except Exception:
            pass

    def run(self) -> None:
        self.root.mainloop()

    def _configure_style(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(
            "Primary.TButton",
            background=PALETTE["accent"],
            foreground="#ffffff",
            borderwidth=0,
            focusthickness=0,
            focuscolor=PALETTE["accent"],
            padding=(14, 9),
            font=("Helvetica", 11, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[("active", PALETTE["accent_hover"]), ("disabled", "#b8c3d9")],
            foreground=[("disabled", "#eef2ff")],
        )

        style.configure(
            "Secondary.TButton",
            background=PALETTE["surface_alt"],
            foreground=PALETTE["text"],
            borderwidth=0,
            focusthickness=0,
            focuscolor=PALETTE["surface_alt"],
            padding=(12, 8),
            font=("Helvetica", 10, "bold"),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#dde6f4"), ("disabled", "#edf1f7")],
            foreground=[("disabled", "#9aa8bc")],
        )

        style.configure(
            "Ghost.TButton",
            background=PALETTE["surface"],
            foreground=PALETTE["muted"],
            borderwidth=0,
            focusthickness=0,
            focuscolor=PALETTE["surface"],
            padding=(10, 7),
            font=("Helvetica", 10, "bold"),
        )
        style.map(
            "Ghost.TButton",
            background=[("active", PALETTE["surface_alt"]), ("disabled", PALETTE["surface"])],
            foreground=[("active", PALETTE["text"]), ("disabled", "#a6b2c4")],
        )

        style.configure(
            "Branch.TEntry",
            fieldbackground="#ffffff",
            foreground=PALETTE["text"],
            bordercolor=PALETTE["surface_edge"],
            lightcolor=PALETTE["surface_edge"],
            darkcolor=PALETTE["surface_edge"],
            insertcolor=PALETTE["text"],
            padding=(10, 8),
        )
        style.map(
            "Branch.TEntry",
            bordercolor=[("focus", PALETTE["accent"])],
            lightcolor=[("focus", PALETTE["accent"])],
            darkcolor=[("focus", PALETTE["accent"])],
        )

        style.configure(
            "Sidebar.Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground=PALETTE["text"],
            borderwidth=0,
            relief="flat",
            rowheight=32,
            font=("Helvetica", 11),
        )
        style.map(
            "Sidebar.Treeview",
            background=[("selected", PALETTE["accent_soft"])],
            foreground=[("selected", PALETTE["text"])],
        )

        style.layout("Sidebar.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    def _build_layout(self) -> None:
        container = tk.Frame(self.root, bg=PALETTE["window"], padx=18, pady=18)
        container.pack(fill="both", expand=True)
        container.grid_columnconfigure(1, weight=1)
        container.grid_rowconfigure(0, weight=1)

        self.sidebar_card = RoundedCard(
            container,
            width=360,
            bg_color=PALETTE["surface"],
            border_color=PALETTE["surface_edge"],
            radius=28,
            padding=22,
        )
        self.sidebar_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.detail_card = RoundedCard(
            container,
            bg_color=PALETTE["surface"],
            border_color=PALETTE["surface_edge"],
            radius=32,
            padding=24,
        )
        self.detail_card.grid(row=0, column=1, sticky="nsew")

        self._build_sidebar(self.sidebar_card.inner)
        self._build_detail(self.detail_card.inner)

    def _build_sidebar(self, parent: tk.Frame) -> None:
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        tree_shell = tk.Frame(parent, bg="#ffffff", highlightbackground=PALETTE["surface_edge"], highlightthickness=1)
        tree_shell.grid(row=0, column=0, sticky="nsew")
        tree_shell.grid_rowconfigure(0, weight=1)
        tree_shell.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            tree_shell,
            style="Sidebar.Treeview",
            show="tree",
            selectmode="browse",
        )
        self.tree.grid(row=0, column=0, sticky="nsew")

        tree_scroll = AutoScrollbar(tree_shell, orient="vertical", command=self.tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.tree.bind("<<TreeviewClose>>", self._on_tree_close)
        self.tree.bind("<Double-1>", lambda _event: self._rename_selected())
        self.tree.bind("<ButtonPress-1>", self._on_tree_press, add="+")
        self.tree.bind("<B1-Motion>", self._on_tree_drag, add="+")
        self.tree.bind("<ButtonRelease-1>", self._on_tree_release, add="+")
        self.tree.bind("<Button-3>", self._show_tree_context_menu, add="+")
        self.tree.bind("<Control-Button-1>", self._show_tree_context_menu, add="+")

        self.tree_context_menu = tk.Menu(self.root, tearoff=0)
        self.tree_context_menu.add_command(label="Rename", command=self._context_rename)
        self.tree_context_menu.add_command(label="New Root", command=self._context_create_root)
        self.tree_context_menu.add_command(label="New Child", command=self._context_create_child)
        self.tree_context_menu.add_separator()
        self.tree_context_menu.add_command(label="Move Up", command=lambda: self._context_move("up"))
        self.tree_context_menu.add_command(label="Move Down", command=lambda: self._context_move("down"))
        self.tree_context_menu.add_command(label="Collapse Branch", command=self._context_toggle_collapse)
        self._collapse_menu_index = self.tree_context_menu.index("end")
        self.tree_context_menu.add_separator()
        self.tree_context_menu.add_command(label="Close", command=self._context_close)

    def _build_detail(self, parent: tk.Frame) -> None:
        parent.grid_rowconfigure(2, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        chrome_bar = tk.Frame(parent, bg=PALETTE["surface"])
        chrome_bar.grid(row=0, column=0, sticky="ew")
        chrome_bar.grid_columnconfigure(1, weight=1)

        dots = tk.Canvas(
            chrome_bar,
            width=70,
            height=18,
            bg=PALETTE["surface"],
            highlightthickness=0,
            bd=0,
        )
        dots.grid(row=0, column=0, sticky="w")
        dots.create_oval(4, 4, 14, 14, fill="#ff605c", outline="")
        dots.create_oval(20, 4, 30, 14, fill="#ffbd44", outline="")
        dots.create_oval(36, 4, 46, 14, fill="#00ca4e", outline="")

        tab_shell = tk.Frame(chrome_bar, bg=PALETTE["surface"])
        tab_shell.grid(row=0, column=1, sticky="e")
        tk.Label(
            tab_shell,
            text="Prototype",
            bg=PALETTE["accent_soft"],
            fg=PALETTE["accent"],
            font=("Helvetica", 9, "bold"),
            padx=12,
            pady=6,
        ).pack(side="left")

        header = tk.Frame(parent, bg=PALETTE["surface"])
        header.grid(row=1, column=0, sticky="ew", pady=(14, 18))
        tk.Label(
            header,
            text="Active Branch",
            bg=PALETTE["surface"],
            fg=PALETTE["muted"],
            font=("Helvetica", 10, "bold"),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            header,
            textvariable=self.active_title,
            bg=PALETTE["surface"],
            fg=PALETTE["text"],
            font=("Helvetica", 24, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(6, 2))
        tk.Label(
            header,
            textvariable=self.active_meta,
            bg=PALETTE["surface"],
            fg=PALETTE["muted"],
            font=("Helvetica", 11),
            anchor="w",
            justify="left",
        ).pack(anchor="w")

        terminal_card = RoundedCard(
            parent,
            bg_color=PALETTE["terminal"],
            border_color=PALETTE["terminal_edge"],
            radius=28,
            padding=0,
        )
        terminal_card.grid(row=2, column=0, sticky="nsew")
        terminal_card.inner.grid_rowconfigure(1, weight=1)
        terminal_card.inner.grid_columnconfigure(0, weight=1)

        terminal_header = tk.Frame(terminal_card.inner, bg=PALETTE["terminal"])
        terminal_header.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))
        terminal_header.grid_columnconfigure(1, weight=1)
        tk.Label(
            terminal_header,
            text="Terminal",
            bg=PALETTE["terminal"],
            fg="#a9b8d3",
            font=("Helvetica", 10, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            terminal_header,
            text="chrome-style shell surface",
            bg=PALETTE["terminal"],
            fg="#7d8ca8",
            font=("Helvetica", 9),
        ).grid(row=0, column=1, sticky="e")

        terminal_shell = tk.Frame(terminal_card.inner, bg=PALETTE["terminal"])
        terminal_shell.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        terminal_shell.grid_rowconfigure(0, weight=1)
        terminal_shell.grid_columnconfigure(0, weight=1)

        self.terminal_font = tkfont.Font(family="Menlo", size=12)
        self.terminal = tk.Text(
            terminal_shell,
            wrap="none",
            undo=False,
            bg=PALETTE["terminal"],
            fg=PALETTE["terminal_text"],
            insertbackground=PALETTE["terminal_cursor"],
            insertwidth=0,
            relief="flat",
            padx=18,
            pady=16,
            font=self.terminal_font,
            highlightthickness=0,
            bd=0,
        )
        self.terminal.grid(row=0, column=0, sticky="nsew")

        y_scroll = AutoScrollbar(terminal_shell, orient="vertical", command=self.terminal.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        self.terminal.configure(yscrollcommand=y_scroll.set)

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
        session_id = self.state.selected_session_id
        node = self.state.node_by_id(session_id)
        if node is None:
            return

        title = simpledialog.askstring("Rename Branch", "Branch name:", initialvalue=node.title, parent=self.root)
        if title is None:
            return

        self.state.rename(session_id, title)
        self._refresh_tree()
        self._refresh_header()

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
        self.tree.insert("", "end", iid=NEW_ROOT_ROW_ID, text="+  New Root")

        if selected and selected != NEW_ROOT_ROW_ID and self.tree.exists(selected):
            self.tree.selection_set(selected)
            self.tree.focus(selected)
            self.tree.see(selected)

        self._refresh_actions()
        self._refresh_header()

    def _insert_branch(self, parent_item: str, parent_id: str | None) -> None:
        for node in self.state.child_nodes(parent_id):
            status = self.state.statuses.get(node.id, "idle")
            label = f"{node.title}    {status}"
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
            self.active_title.set("No branch selected")
            self.active_meta.set("Create a root branch to start a new workspace thread.")
            return

        status = self.state.statuses.get(node.id, "idle")
        self.active_title.set(node.title)
        self.active_meta.set(f"Status: {status}   Initial cwd: {node.initial_cwd}")

    def _refresh_terminal_view(self) -> None:
        session_id = self.state.selected_session_id
        buffer = self.state.terminal_buffers.get(session_id or "", "")

        # Skip if nothing changed
        if (
            session_id == self._displayed_session_id
            and buffer == self._displayed_buffer
        ):
            return

        session_changed = session_id != self._displayed_session_id
        old_buffer = self._displayed_buffer if not session_changed else None
        self._displayed_session_id = session_id
        self._displayed_buffer = buffer

        if old_buffer is not None and old_buffer and buffer:
            # Incremental update: find divergence point to avoid full redraw flicker
            common = 0
            limit = min(len(buffer), len(old_buffer))
            while common < limit and buffer[common] == old_buffer[common]:
                common += 1

            if common < len(old_buffer):
                # Delete from divergence point onward
                prefix = old_buffer[:common]
                line = prefix.count("\n") + 1
                col = common - prefix.rfind("\n") - 1
                self.terminal.delete(f"{line}.{col}", "end")

            tail = buffer[common:]
            if tail:
                self.terminal.insert("end", tail)
        else:
            # Full replacement (session switch or empty buffers)
            self.terminal.delete("1.0", "end")
            if buffer:
                self.terminal.insert("end", buffer)

        self.terminal.see("end")
        self._refresh_header()
        self._refresh_actions()

    def _refresh_actions(self) -> None:
        has_selection = self.state.selected_session_id is not None
        _ = has_selection

    def _on_tree_select(self, _event: tk.Event) -> None:
        if self._drag_active:
            return
        selection = self.tree.selection()
        session_id = selection[0] if selection else None
        if session_id == NEW_ROOT_ROW_ID:
            self._create_root()
            return
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
        cols = max((self.terminal.winfo_width() - 36) // char_width, 20)
        rows = max((self.terminal.winfo_height() - 32) // line_height, 8)
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

    def _on_tree_press(self, event: tk.Event) -> None:
        item_id = self.tree.identify_row(event.y)
        if item_id == NEW_ROOT_ROW_ID:
            self._drag_session_id = None
            self._drag_target_id = None
            self._drag_start_xy = None
            self._drag_active = False
            return
        self._drag_session_id = item_id or None
        self._drag_target_id = None
        self._drag_drop_mode = "sibling"
        self._drag_start_xy = (event.x, event.y)
        self._drag_active = False

    def _on_tree_drag(self, event: tk.Event) -> None:
        if self._drag_session_id is None or self._drag_start_xy is None:
            return

        dx = event.x - self._drag_start_xy[0]
        dy = event.y - self._drag_start_xy[1]
        if not self._drag_active and abs(dx) + abs(dy) < 8:
            return

        self._drag_active = True
        target_id = self.tree.identify_row(event.y) or None
        if target_id == NEW_ROOT_ROW_ID:
            target_id = None
        self._drag_target_id = target_id
        self._drag_drop_mode = self._infer_drop_mode(target_id, event.x)

        if self._drag_drop_mode == "root" or target_id is None:
            self.tree.selection_set(self._drag_session_id)
            return

        if target_id == self._drag_session_id:
            self.tree.selection_set(self._drag_session_id)
            return

        self.tree.selection_set(target_id)
        target = self.state.node_by_id(target_id)
        if target is None:
            return

    def _on_tree_release(self, _event: tk.Event) -> None:
        if self._drag_session_id is None:
            return

        source_id = self._drag_session_id
        target_id = self._drag_target_id
        drop_mode = self._drag_drop_mode
        was_dragging = self._drag_active
        self._reset_drag_state()

        if not was_dragging:
            return

        moved = self.state.move_relative_to_target(source_id, target_id, drop_mode)
        self._refresh_tree()
        self._focus_session(source_id)
        _ = moved

    def _infer_drop_mode(self, target_id: str | None, x_position: int) -> str:
        if target_id is None:
            return "root"

        bbox = self.tree.bbox(target_id)
        if not bbox:
            return "root"

        item_x, _item_y, _item_width, _item_height = bbox
        if x_position <= 28:
            return "root"
        if x_position >= item_x + 28:
            return "child"
        return "sibling"

    def _reset_drag_state(self) -> None:
        self._drag_session_id = None
        self._drag_target_id = None
        self._drag_drop_mode = "sibling"
        self._drag_start_xy = None
        self._drag_active = False

    def _show_tree_context_menu(self, event: tk.Event) -> str:
        target_id = self.tree.identify_row(event.y) or None
        if target_id == NEW_ROOT_ROW_ID:
            target_id = None
        self._context_target_id = target_id

        if target_id is not None:
            self.tree.selection_set(target_id)
            self.tree.focus(target_id)
            self.state.select(target_id)
            self._refresh_terminal_view()
        else:
            self.tree.selection_remove(*self.tree.selection())

        has_target = target_id is not None
        target = self.state.node_by_id(target_id)
        child_state = "normal" if has_target else "disabled"
        target_state = "normal" if has_target else "disabled"
        collapse_label = "Collapse Branch"
        if target is not None and target.is_collapsed:
            collapse_label = "Expand Branch"

        self.tree_context_menu.entryconfigure("Rename", state=target_state)
        self.tree_context_menu.entryconfigure("New Child", state=child_state)
        self.tree_context_menu.entryconfigure("Move Up", state=target_state)
        self.tree_context_menu.entryconfigure("Move Down", state=target_state)
        self.tree_context_menu.entryconfigure("Close", state=target_state)
        self.tree_context_menu.entryconfigure(self._collapse_menu_index, state=target_state, label=collapse_label)

        try:
            self.tree_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.tree_context_menu.grab_release()

        return "break"

    def _context_create_root(self) -> None:
        self._context_target_id = None
        session_id = self.state.create_root_session()
        self._refresh_tree()
        self._focus_session(session_id)

    def _context_create_child(self) -> None:
        if self._context_target_id is None:
            return

        session_id = self.state.create_child_session_under(self._context_target_id)
        self._context_target_id = None
        if session_id is None:
            return

        self._refresh_tree()
        self._focus_session(session_id)

    def _context_rename(self) -> None:
        if self._context_target_id is None:
            return

        self._focus_session(self._context_target_id)
        self._rename_selected()

    def _context_move(self, direction: str) -> None:
        if self._context_target_id is None:
            return

        self.state.move(self._context_target_id, direction)
        self._refresh_tree()
        self._focus_session(self._context_target_id)

    def _context_toggle_collapse(self) -> None:
        if self._context_target_id is None:
            return

        node = self.state.node_by_id(self._context_target_id)
        if node is None:
            return

        self.state.set_collapsed(node.id, not node.is_collapsed)
        self._refresh_tree()
        self._focus_session(node.id)

    def _context_close(self) -> None:
        if self._context_target_id is None:
            return

        closing_id = self._context_target_id
        self._context_target_id = None
        self.state.close(closing_id)
        self._refresh_tree()
        self._refresh_terminal_view()


def main() -> None:
    RapunzelUI().run()
