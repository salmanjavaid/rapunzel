# Rapunzel

Rapunzel is a Python-first prototype of a tree-based terminal workspace manager.

This version is designed to be easy to run from VS Code while the product shape is still being proven. It keeps the core idea from the design notes:

- root sessions
- child sessions
- collapsible sidebar tree
- workspace restore
- PTY-backed shell sessions

## Run

Use the system Python that already has `tkinter` available:

```bash
python3 app.py
```

## What This Prototype Includes

- Tk desktop UI with a session tree on the left
- PTY-backed interactive shell sessions on macOS and Linux
- create root and child sessions
- rename, reorder, collapse, and close sessions
- workspace persistence to `~/.rapunzel/workspace.json`

## Current Limitations

- The terminal pane is a basic text-backed PTY viewer, not a full terminal emulator.
- ANSI-heavy apps and advanced cursor control will not render perfectly yet.
- Current working directory tracking is still basic, so child sessions inherit the last stored cwd rather than a live shell cwd probe.

## Code Layout

- `app.py`: entrypoint
- `rapunzel/models.py`: persisted workspace models
- `rapunzel/store.py`: workspace JSON load/save
- `rapunzel/session.py`: PTY shell runtime
- `rapunzel/state.py`: app state and session lifecycle
- `rapunzel/ui.py`: Tk UI
- `FEATURE_TRACKER.md`: running feature log for this prototype
- `terminal-tree-app-design.md`: product design notes
