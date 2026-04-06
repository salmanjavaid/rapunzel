# Feature Tracker

This directory is currently being developed without git history in the folder itself.
Until the project is initialized as a repository, this file is the running feature log.

## Current Status

Prototype stage. The app is a Python/Tk desktop prototype focused on validating the tree-based terminal workflow before a heavier implementation.

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

## Known Gaps

- The terminal pane is still not a full terminal emulator.
- Advanced TUI apps like `vim`, `htop`, or rich prompt redraws will still be incomplete.
- Current working directory tracking is still basic.

## Next Candidate Features

- Stronger terminal emulation
- live cwd tracking
- branch duplication or restart
- keyboard tree navigation
- better session status indicators
- repo initialization with commits so feature tracking is both in markdown and in git history

## Update Rule

Whenever a user-facing feature or behavior changes, append a short dated note here.
