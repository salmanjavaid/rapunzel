# Project Status

This file is the current implementation summary for the Rapunzel prototype.

For the full canonical write-up, use `ARCHITECTURE_AND_PROGRESS.md`.

It answers three practical questions:

1. What is already built?
2. What changed recently?
3. What should happen next?

## Current Product Direction

Rapunzel is a tree-based terminal workspace manager with:

- root branches
- child branches
- persistent branch state
- one active terminal pane on the right
- an embedded web UI as the primary product path

The Tk UI remains in the repo as fallback code, but the active architecture is:

`app.py` -> `rapunzel/web_ui.py` -> `webui/dist/index.html`

## What Is Already Built

### Branch Management

- create root branches
- create child branches
- rename branches
- move branches up and down among siblings
- collapse and expand branches
- close a single branch
- close a branch subtree
- context-menu actions in the web UI
- selected-branch toolbar actions in the web UI

### Tree And Window UI

- left-side branch tree
- active branch header and metadata
- rounded browser-style shell layout
- embedded webview host window
- one active terminal pane on the right
- macOS host currently forced onto Qt-backed `pywebview` (`PySide6`)

### Session Runtime

- PTY-backed shell sessions
- workspace persistence to `~/.rapunzel/workspace.json`
- workspace restore on launch
- selected-branch terminal switching
- per-session transcript capture
- per-session status tracking
- terminal resize propagation

### Terminal Architecture

- `xterm.js` embedded directly in the app window
- `pyte`-based backend terminal state model
- backend-rendered terminal snapshots for selected-session hydration
- simplified shell startup for cleaner prompts and more predictable embedding

## Current Architecture Summary

### Backend

Main files:

- `rapunzel/models.py`
- `rapunzel/store.py`
- `rapunzel/state.py`
- `rapunzel/session.py`
- `rapunzel/terminal_screen.py`

Current backend shape:

- workspace structure is stored as a flat list of nodes
- frontend receives a nested serialized tree
- `AppState` owns tree state, runtime sessions, transcripts, statuses, and output events
- `PTYSession` manages the live shell process, PTY I/O, and resize events

### Host And Bridge

Main file:

- `rapunzel/web_ui.py`

Current host behavior:

- boots the workspace store and app state
- creates the `pywebview` desktop shell
- exposes a JS bridge for state reads and mutating actions

### Frontend

Main files:

- `webui/src/app.js`
- `webui/src/styles.css`

Current frontend behavior:

- renders the tree
- renders the active terminal
- hydrates selected sessions from the backend terminal snapshot
- receives live PTY output through direct push handlers
- applies action responses directly from bridge return payloads

## Important Recent Changes

### Embedded-Terminal Path Is The Main Architecture

The major architectural shift has already happened:

- the selected shell now lives inside embedded `xterm.js`
- the older Tk text rendering path is no longer the main product direction

This was the correct move and should remain the default path.

### Context-Menu Close Investigation

We investigated a bug where context-menu actions appeared to require two clicks.

What the debugging showed:

- the first click was reaching the frontend handler
- the frontend was calling backend close on the first click
- the delay was inside backend session teardown

Retained fixes from that work:

1. frontend action handlers now apply the returned UI payload directly instead of always doing a separate `get_ui_state()` fetch
2. backend close operations now remove sessions from app state immediately and tear down PTYs asynchronously

That means the close-action debugging changed real architecture, not just temporary behavior.

## What Is Still Limited

### Replay Fidelity

Session hydration still depends on a backend-rendered terminal snapshot into a single visible terminal.

That means:

- wrapping after repeated resizes can still be imperfect
- snapshot fidelity is weaker than keeping a fully live terminal surface per branch

### Tree Interaction Parity

The older Tk prototype had richer tree movement behavior. The web UI still needs parity work, especially around drag-and-drop movement.

### cwd Tracking

Current working directory tracking is still basic, so child branches inherit stored cwd information rather than a stronger live shell cwd source.

### Platform Constraints

The macOS host path currently depends on Qt-backed `pywebview`, not Cocoa.

## What Should Happen Next

### Highest Priority

Continue from the embedded-terminal architecture and close the remaining integration gaps.

The main work now is:

- harden terminal replay behavior
- finish tree UX parity in the web UI
- validate more interactive workloads inside the embedded terminal

### Recommended Order

1. Verify the shutdown hardening across more shell/process combinations.
2. Port remaining drag/drop tree interactions into the web UI.
3. Improve replay behavior for sessions that have seen multiple resizes.
4. Add stronger cwd tracking so child branches inherit real shell location.
5. Validate `vim`, `htop`, and similar TUIs inside the embedded terminal path.

## Current Recommendation

Do not invest further in the Tk text renderer as the main product path.

The correct direction is to keep building on the current stack:

- `pywebview`
- `xterm.js`
- PTY-backed shell sessions
- persisted branch tree state
