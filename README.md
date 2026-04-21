# Rapunzel

Rapunzel is a tree-based terminal workspace manager.

Each branch is a shell session. Branches can be roots or children, one branch is active in the main terminal pane at a time, and the workspace tree is restored across launches.

The current primary product path is the embedded web UI hosted in `pywebview`. The older Tk UI still exists as fallback code, but it is no longer the main architecture.

## Run

Clone the repo, create a virtual environment, install the Python and Node dependencies, then build the frontend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
npm run build:webui
python3 app.py
```

Prerequisites:

- Python 3
- Node.js and npm

Notes:

- `pip install -r requirements.txt` installs the runtime Python dependencies
- `npm run build:webui` generates `webui/dist/app.js`
- `python3 app.py` launches the desktop app from source
- on Apple Silicon Macs, Rapunzel shell sessions wrap `brew` so Homebrew commands are forwarded through native `arm64` automatically
- the code still supports repo-local `.deps/` if present, but a virtual environment is the recommended setup for development and open-source use

## Build macOS App

The repository also includes a local macOS packaging script used during development. Running from source is the primary open-source path.

If you want to try the macOS bundle build, first install the runtime dependencies above and ensure `PyInstaller` is available in your active Python environment, then run:

```bash
pip install pyinstaller
bash build_macos_app.sh
```

Output:

- `dist/Rapunzel.app`

Notes:

- the packaging path is macOS-specific
- the app bundle is signed ad hoc during the build so it launches more cleanly on macOS

## Architecture

The app is split into four layers:

1. Python entrypoint and host window
2. Python application state and PTY runtime
3. JS bridge between Python and the web UI
4. Embedded frontend tree and terminal UI

Default runtime path:

`app.py` -> `rapunzel/web_ui.py` -> `webui/dist/index.html`

### Backend

- `rapunzel/models.py`: `SessionNode` and `WorkspaceSnapshot`
- `rapunzel/store.py`: workspace JSON load/save
- `rapunzel/state.py`: app state, branch lifecycle, event queue, transcript state
- `rapunzel/session.py`: PTY-backed shell runtime
- `rapunzel/terminal_screen.py`: `pyte`-based terminal state model

Important backend details:

- branch data is stored as a flat list of nodes and serialized into a nested tree for the frontend
- sessions are PTY-backed interactive shells
- terminal output is pushed from Python into the frontend
- selected-session hydration uses a backend-rendered terminal snapshot before live PTY output takes over
- close operations remove sessions from app state immediately and tear down PTYs without hanging app shutdown

### Web Host

- `rapunzel/web_ui.py`: creates the `pywebview` window and exposes `RapunzelBridge`

The bridge exposes methods for:

- loading UI state
- session snapshot fetch
- select/create/rename/move/collapse/close operations
- sending input
- resizing sessions

On macOS, the app currently forces `pywebview` to use the Qt backend (`PySide6`) because the Cocoa backend was unstable in this environment.

### Frontend

- `webui/src/app.js`: state, tree rendering, context menu, bridge calls, `xterm.js`
- `webui/src/styles.css`: app styling
- `webui/dist/`: built frontend assets

Frontend behavior:

- renders the branch tree on the left
- renders one active `xterm.js` terminal on the right
- applies action responses directly from bridge return payloads
- hydrates selected sessions from the backend terminal snapshot
- receives live PTY output via bridge push handlers

## What Is Built

- pywebview desktop shell with embedded `xterm.js`
- PTY-backed interactive shell sessions
- root and child branches
- branch selection
- rename
- move up/down among siblings
- collapse and expand
- close tab
- close branch
- context menu actions
- workspace persistence to `~/.rapunzel/workspace.json`
- restore of saved workspace tree on launch

## Important Recent Work

- moved the product path onto the embedded web UI with `xterm.js`
- kept the older Tk UI as fallback only
- changed frontend actions to apply returned UI payloads directly instead of always doing a second state fetch
- hardened session close behavior so PTY shutdown no longer hangs the whole app
- added runtime and bundle icon wiring so the app icon appears in source runs and macOS builds

Those changes were introduced while stabilizing the embedded-terminal path for real use.

## Current Limitations

- first-load session hydration still depends on backend snapshot fidelity, so resize-heavy history can still be imperfect
- drag-and-drop tree parity from the older Tk prototype is still incomplete in the web UI
- cwd tracking is still basic
- the macOS host path currently depends on Qt-backed `pywebview`

## Code Layout

- `app.py`: entrypoint
- `rapunzel/models.py`: persisted workspace models
- `rapunzel/store.py`: workspace JSON load/save
- `rapunzel/session.py`: PTY shell runtime
- `rapunzel/state.py`: app state and session lifecycle
- `rapunzel/web_ui.py`: pywebview host window and JS bridge
- `rapunzel/ui.py`: legacy Tk fallback UI
- `webui/`: embedded frontend assets for the tree and terminal
- `PROJECT_STATUS.md`: implementation status and next work
- `ARCHITECTURE_AND_PROGRESS.md`: canonical architecture, progress, and debugging history
- `FEATURE_TRACKER.md`: running feature log
- `terminal-tree-app-design.md`: product design notes
