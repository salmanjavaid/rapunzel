# Feature Tracker

This directory is currently being developed without git history in the folder itself.
Until the project is initialized as a repository, this file is the running feature log.

## Current Status

Prototype stage. The app is now a Python desktop prototype with a pywebview shell and embedded `xterm.js` terminal, focused on validating the tree-based terminal workflow before a heavier implementation.

## Implemented

### 2026-04-06

- Cleaned the directory down to the Python prototype, README, and design notes.
- Rebuilt the app as a Python-first project with a simple `python3 app.py` entrypoint.
- Added a sidebar tree for root and child sessions.
- Added session persistence to `~/.rapunzel/workspace.json`.
- Added PTY-backed shell sessions for macOS/Linux.
- Added branch operations: create root, create child, reorder, collapse, close.
- Added branch renaming through a dedicated sidebar name field with Enter/apply behavior.
- Improved terminal rendering so shell-style backspace and common cursor movement behave correctly.
- Initialized this folder as a git repository on `main` so code history is now tracked in commits.
- Restyled the Tk UI with a softer browser-like layout, rounded card surfaces, and a chrome-inspired header/terminal shell.
- Fixed a Tk layout crash in the redesigned UI caused by an invalid label padding value.
- Added drag-and-drop tree movement so branches can be reordered and reparented between root and child levels.
- Added explicit drag-outdent behavior so a child branch can become a root by dropping far enough left.
- Added right-click tree actions so users can start a new root or child directly from a branch context menu.
- Expanded the right-click tree menu with rename, move, collapse/expand, and close actions.
- Simplified the sidebar by removing the button/header/control stack above the tree and relying on context menu plus shortcuts instead.
- Added a `+` button in the chrome/tab strip to create a new root branch directly.
- Made the chrome-strip `+` button visually explicit so it reads as a real new-root control.
- Moved the `+` new-root control into the left tree as the last tab row, matching the tab list location.
- Switched tree and terminal scrollbars to auto-hide so they only appear when content overflows.
- Enabled soft wrapping in the terminal pane and removed the horizontal scrollbar path.
- Fixed terminal width tracking so long prompts/input wrap against real terminal columns instead of drifting off-screen.
- Removed widget-level text wrapping so the terminal view no longer double-wraps lines already wrapped by the terminal screen model.
- Replaced the hand-rolled terminal parser with a `pyte`-based terminal emulation layer loaded from local project dependencies.
- Switched Rapunzel shell sessions to app-specific minimal shell startup files so prompts and line editing are simpler and more controlled.
- Replaced the default Tk terminal surface with an embedded `xterm.js` terminal inside a pywebview host window, driven by raw PTY transcript replay from the Python backend.
- Moved the active UI entrypoint to the webview app while keeping the older Tk UI available as a fallback module.
- Installed and selected the Qt backend (`PySide6` via `pywebview`) on macOS because the Cocoa backend was not stable in this environment.

### 2026-04-08

- Ported the right-click branch context menu into the web UI with logical action enablement for new root, new child, rename, move, collapse/expand, and close.

### 2026-04-20

- Restored the web terminal screen model to a `pyte`-backed implementation so PTY resize handling and redraw-heavy chat CLIs hydrate from a stable rendered screen instead of a broken hand-rolled parser.
- Changed first-load terminal hydration in the web UI to use the backend's rendered screen snapshot, reducing duplicated redraw history when conversing with terminal-based AI tools.
- Tightened the web UI layout so the active conversation surface gets more space and less decorative chrome.

### 2026-04-21

- Fixed app shutdown hangs caused by PTY close on macOS: the reader thread now uses a timed `select` loop, and session teardown closes the PTY safely before escalating from `SIGHUP` to `SIGTERM` and `SIGKILL` if needed.
- Added app icon wiring for both source runs and macOS bundle builds, using the repo's `icon.png` and generating `.icns` build assets automatically.
- Set the application icon explicitly for source runs on Qt/macOS so the app icon shows in the Dock/taskbar even when launched from VS Code instead of only from a packaged bundle.

## Known Gaps

- Drag-and-drop branch movement is not yet ported into the web UI.
- Transcript replay after historical resizes can still differ from the exact original wrap state.
- Current working directory tracking is still basic.

## Next Candidate Features

- Stronger terminal emulation
- live cwd tracking
- branch duplication or restart
- keyboard tree navigation
- better session status indicators

## Update Rule

Whenever a user-facing feature or behavior changes, append a short dated note here.
