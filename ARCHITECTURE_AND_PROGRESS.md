# Rapunzel Architecture And Progress

## Summary

Rapunzel is a tree-based terminal workspace manager.

Core model:

- each branch is a shell session
- branches can be roots or children
- one branch is active in the terminal pane at a time
- branch tree and selection persist across launches

Primary product path:

`app.py` -> `rapunzel/web_ui.py` -> `webui/dist/index.html`

The Tk UI still exists as fallback code, but the real product path is the `pywebview` + `xterm.js` stack.

## System Map

### Entry Point

- `app.py`

Behavior:

- adds `.deps/` to `sys.path` if present
- launches `rapunzel.web_ui.main`
- falls back to `rapunzel.ui.main` if web UI startup fails

### Backend

- `rapunzel/models.py`
- `rapunzel/store.py`
- `rapunzel/state.py`
- `rapunzel/session.py`
- `rapunzel/terminal_screen.py`

Responsibilities:

- persist branch tree and selected branch
- create and manage PTY-backed shell sessions
- track transcript, screen state, and status per session
- expose serialized UI state to the frontend
- queue output and exit events for polling

Important backend shape:

- branch structure is stored as a flat list of nodes using `parent_id`
- frontend receives a nested serialized tree
- PTY runtime is separate from persisted workspace structure

### Host And Bridge

- `rapunzel/web_ui.py`

Responsibilities:

- create `WorkspaceStore`
- create `AppState`
- bootstrap saved sessions
- create the `pywebview` window
- expose `RapunzelBridge` methods to JavaScript

Bridge methods cover:

- UI state fetch
- output polling
- transcript fetch
- select/create/rename/move/collapse/close actions
- input forwarding
- resize propagation

Platform note:

- macOS currently forces Qt-backed `pywebview` via `PySide6`
- Cocoa backend was unstable in this environment

### Frontend

- `webui/src/app.js`
- `webui/src/styles.css`
- `webui/dist/`

Responsibilities:

- render the branch tree
- render the active branch header
- host the visible `xterm.js` terminal
- dispatch actions through the bridge
- hydrate the selected session from the backend-rendered terminal snapshot
- receive live PTY output through bridge push handlers

## Main Data Flow

### Startup

1. `app.py` launches the web host.
2. `RapunzelBridge` creates `WorkspaceStore` and `AppState`.
3. `AppState.bootstrap()` loads saved nodes and recreates PTY sessions.
4. `pywebview` loads `webui/dist/index.html`.
5. Frontend calls `get_ui_state()` and renders tree plus terminal shell.

### Terminal Output

1. Shell writes to PTY.
2. `PTYSession._read_loop()` reads bytes.
3. Backend updates screen state and pushes active output toward the frontend.
4. Frontend writes live PTY output into `xterm.js`.

### Terminal Input

1. User types in `xterm.js`.
2. Frontend calls `send_input(...)`.
3. Bridge forwards data to `AppState.send_input(...)`.
4. Backend writes bytes to the PTY.

### Resize

1. Frontend fits the terminal with `FitAddon`.
2. Frontend calls `resize_session(...)`.
3. Backend updates `TerminalScreen`.
4. Backend resizes the PTY with `TIOCSWINSZ`.

### Session Actions

For create, select, rename, move, collapse, and close:

1. Frontend calls a bridge method.
2. Backend mutates `AppState`.
3. Bridge returns updated UI payload.
4. Frontend applies that payload directly.

That direct-return pattern is now important and intentional.

## What Is Built

### Branch Workflow

- create root branches
- create child branches
- select branches
- rename branches
- move branches up and down among siblings
- collapse and expand branches
- close a single branch
- close a branch subtree
- context-menu actions in the web UI
- selected-branch toolbar actions in the web UI

### Terminal Workflow

- PTY-backed interactive shell sessions
- transcript capture
- status tracking
- resize propagation
- selected-session hydration into embedded `xterm.js`
- workspace restore on relaunch

### Host UI

- left-side branch tree
- active branch header and metadata
- one visible terminal pane on the right
- rounded browser-style host window
- `pywebview` desktop shell

## Important Decisions And Retained Fixes

### Embedded Terminal Is The Main Path

The product should continue on:

- `pywebview`
- `xterm.js`
- PTY-backed shell sessions

Do not move back toward the Tk text-rendering path as the main product direction.

### Direct UI Application From Bridge Responses

Frontend action handlers now apply the returned UI payload directly instead of always doing a second `get_ui_state()` fetch.

Why it matters:

- reduces refresh races
- makes action results visible immediately
- simplifies the action-update path

Main file:

- `webui/src/app.js`

### Live Frontend Terminal Instances For Visited Sessions

Frontend terminal switching now keeps a live `xterm.js` instance per visited session in memory and toggles visibility between them, instead of always reconstructing the active view from scratch on every switch.

Why it matters:

- reduces dependence on transcript replay during normal switching
- preserves more live terminal state in the current app session
- moves Rapunzel incrementally closer to the way mature terminal products like VS Code feel

Current limitation:

- first hydration for a session still uses a backend-rendered terminal snapshot
- unvisited sessions are not fully live until selected once

Main file:

- `webui/src/app.js`

### Asynchronous Runtime Teardown On Close

Close operations now:

- remove the session from app state immediately
- persist the updated tree immediately
- tear down the PTY runtime asynchronously in the background

Why it matters:

- shutdown should not hang even if the foreground process ignores `SIGTERM`
- UI should not block on runtime teardown

Main file:

- `rapunzel/state.py`

### Live cwd Tracking For Child Session Inheritance

Shell startup now emits cwd markers in prompt hooks, and backend output parsing updates each session's `last_known_cwd`.

Why it matters:

- child sessions can inherit the parent session's real current folder
- branch creation behavior matches actual shell navigation more closely

Main files:

- `rapunzel/session.py`
- `rapunzel/state.py`

## Close-Action Debugging Outcome

Observed issue:

- context-menu actions appeared to require two clicks

What we proved:

- the first click was reaching the frontend handler
- the frontend was calling backend close on the first click
- the actual delay was in backend session teardown

Root cause:

- synchronous PTY shutdown blocked the close path long enough that the first action looked ignored

Architectural changes kept from that debugging work:

1. direct frontend application of returned UI payloads
2. async PTY teardown after state mutation

## Current Limitations

### Replay Fidelity

Session hydration still depends on backend snapshot restoration into one visible terminal.

Implications:

- resize history can produce imperfect snapshot restoration
- fidelity is weaker than keeping one fully live terminal surface per branch

### cwd Tracking

Child sessions inherit stored cwd information, not a robust live cwd probe.

### Tree Interaction Parity

The web UI still lacks full parity with the richer tree interactions from the older Tk prototype, especially drag-and-drop movement.

### Platform Dependence

The macOS host path currently depends on Qt-backed `pywebview`, not Cocoa.

## Files That Matter Most

For backend/session lifecycle:

- `rapunzel/state.py`
- `rapunzel/session.py`
- `rapunzel/web_ui.py`

For frontend behavior:

- `webui/src/app.js`
- `webui/src/styles.css`

For persistence and models:

- `rapunzel/models.py`
- `rapunzel/store.py`

## Recommended Next Work

1. Verify the shutdown behavior against more shell and process-tree cases.
2. Port remaining drag/drop tree interactions into the web UI.
3. Improve replay behavior across repeated terminal resizes.
4. Add stronger live cwd tracking for child-session inheritance.
5. Test more interactive TUIs end to end inside the embedded terminal path.
