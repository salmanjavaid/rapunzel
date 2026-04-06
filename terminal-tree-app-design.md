# Terminal Tree App Design

## 1. Purpose

This document describes a standalone desktop application for managing terminal sessions in a tree, similar in spirit to Tree Style Tab in Firefox.

The core problem it solves is simple:

- Traditional terminal applications usually show sessions as a flat row of tabs.
- Flat tabs work poorly when many sessions are related to each other.
- When working on multiple threads of work, people mentally group terminals into parent/child relationships even though the UI does not.

This app makes that structure visible.

Instead of flat tabs, the app shows a collapsible tree in a left sidebar:

- A root session is the start of a line of work.
- A child session is spawned from an existing session.
- Related sessions stay grouped together.
- The user can collapse or expand branches to reduce clutter.

For version 1, this is a generic terminal workspace manager.

It is **not** agent-aware.
It does **not** know what Codex, Claude, Gemini, or any other tool is doing.
Each node is only a normal shell session backed by a PTY.

## 2. Product Summary

The application has two main regions:

- Left sidebar: a tree of terminal sessions
- Main pane: the currently selected terminal

Each item in the tree represents one live or restorable terminal session.

The app supports:

- Creating a new root session
- Creating a child session from the selected session
- Selecting a session to view it
- Renaming a session
- Reordering sessions within the tree
- Collapsing and expanding branches
- Closing a session
- Restoring the workspace structure when the app reopens

## 3. Main Design Principles

The app should follow these principles:

### 3.1 Tree First

The tree is the primary organizing concept, not an afterthought.

This means:

- The sidebar is always visible unless explicitly hidden later.
- Session lineage is visible and easy to follow.
- Child sessions should visually feel attached to their parent.

### 3.2 Terminal Ownership

The app should own the terminal sessions directly using PTYs.

This means:

- The app does not wrap iTerm, Terminal.app, or another terminal application.
- The app launches shells itself.
- The app controls session lifecycle, metadata, and rendering.

This is important because external terminal applications do not expose a clean, reliable tree model.

### 3.3 Keyboard Friendly

People using many terminals usually prefer keyboard workflows.

Version 1 should support:

- Up/down tree navigation
- Expand/collapse branch with keyboard
- Create root session with shortcut
- Create child session with shortcut
- Close selected session with shortcut
- Quick rename selected session

### 3.4 Predictable, Not Clever

The app should not guess too much.

Examples:

- A child session inherits the parent session's current working directory if known.
- A renamed session keeps the user-provided name until changed again.
- Closing a parent should not silently delete all children.

Behavior should be explicit and consistent.

## 4. Non-Goals for Version 1

These ideas may be useful later, but should not be in the initial version:

- AI or agent awareness
- Prompt history management
- Model/token tracking
- Split panes
- Collaboration or shared sessions
- Remote session management
- SSH profile management
- Saved commands / macros
- tmux integration as a required dependency
- Full session replay

Avoiding these in V1 matters because they add complexity before the core tree workflow is proven.

## 5. User Experience

### 5.1 Window Layout

The initial layout:

- Left sidebar: tree of sessions
- Main content area: terminal emulator for the selected session

The sidebar should show for each node:

- A disclosure icon if the session has children
- The session title
- Optional small status marker

Possible status markers:

- Running
- Exited
- Error

For V1, a simple visual state is enough.

### 5.2 Session Titles

Each session has a title.

Default title behavior:

- New root session: `Shell 1`, `Shell 2`, `Shell 3`, etc.
- New child session: `Shell 4`, `Shell 5`, etc.

Renaming behavior:

- The user can rename any session.
- After renaming, the custom title is stored.
- The app should not overwrite a custom title automatically.

### 5.3 Session Selection

When the user clicks a node in the sidebar:

- That session becomes selected.
- The main pane switches to that terminal.
- Keyboard input is directed to that terminal when it is focused.

Selecting a different node does not restart the session.
It only changes which session is visible.

### 5.4 Root Sessions

A root session is a top-level item in the tree.

Creating a root session:

- User triggers `New Root Session`
- App creates a new PTY
- App launches the configured shell
- App inserts the session at the bottom of the root list
- App selects it automatically

### 5.5 Child Sessions

A child session belongs under an existing session.

Creating a child session:

- User selects an existing node
- User triggers `New Child Session`
- App determines the best cwd for the child
- App creates a new PTY using that cwd
- App inserts the new node as the last child of the selected node
- Parent node expands automatically if collapsed
- New child becomes selected

Expected cwd behavior:

- If the parent session's current working directory is known, use it
- Otherwise use the workspace default cwd

Important note:

Tracking a terminal's current working directory is not trivial because shells can `cd` at any time.
The implementation should support a practical approach, described later in this document.

### 5.6 Collapse and Expand

Each node with children can be collapsed or expanded.

When collapsed:

- Children are hidden in the sidebar
- The child sessions themselves remain alive
- Terminal processes keep running

Collapse is a visual state only.
It must never suspend or kill child sessions.

### 5.7 Reordering

Users should be able to reorder:

- Root sessions among other roots
- Children among siblings under the same parent

For V1, do **not** allow arbitrary drag across unrelated levels if it makes behavior ambiguous.

Recommended rule:

- Reorder within the same parent only

This is simpler, easier to explain, and reduces accidental tree corruption.

### 5.8 Closing Sessions

Closing a session needs careful behavior.

Rules for V1:

- If a leaf session is closed, remove it from the tree
- If a session with children is closed, do not silently delete the entire branch

Recommended behavior for a parent with children:

- Show a confirmation dialog
- Offer: `Close this session only and promote children`
- Offer: `Cancel`

When promoting children:

- If the closed node had a parent, its children become children of that parent
- If the closed node was a root, its children become root nodes

This preserves structure and avoids destructive surprises.

### 5.9 App Restart and Restore

The app should restore workspace metadata when relaunched.

Important distinction:

- The tree structure and metadata should be restored
- Live shell processes usually should not be expected to survive a full app exit in V1

So after restart:

- The app restores the tree layout
- Sessions are marked as restorable records
- The app can either auto-relaunch shells or mark them as exited and let the user reopen

Recommended V1 behavior:

- Restore the tree and session titles
- Restore which branches were collapsed
- Restore parent/child relationships
- Recreate the shell processes fresh on launch

Reason:

- True process persistence across full app shutdown is much harder
- Relaunching is understandable and much simpler to implement

The doc should be clear with users that "restore workspace" means "restore structure", not "continue the exact previous process state."

## 6. Technical Architecture

## 6.1 Recommended Stack

Recommended technology choices:

- Electron for desktop shell
- React for UI
- xterm.js for terminal rendering
- node-pty for PTY creation and shell process management
- SQLite for persistent workspace metadata

Why this stack:

- Electron has mature PTY integration patterns
- xterm.js is widely used and proven
- node-pty is a common solution for shell-backed terminal apps
- SQLite is simple, local, reliable, and easy to inspect

### 6.2 High-Level Components

The app can be understood as five major pieces:

1. UI shell
2. Tree state manager
3. PTY/session manager
4. Persistence layer
5. IPC bridge

#### UI shell

Responsible for:

- Rendering sidebar tree
- Rendering active terminal view
- Keyboard shortcuts
- Dialogs and rename flows

#### Tree state manager

Responsible for:

- In-memory node hierarchy
- Selection state
- Expanded/collapsed state
- Reordering rules
- Close/promote behavior

#### PTY/session manager

Responsible for:

- Starting shell processes
- Tracking process lifecycle
- Sending user input to PTYs
- Streaming PTY output to the terminal view
- Detecting exits

#### Persistence layer

Responsible for:

- Saving session metadata
- Saving tree relationships
- Saving UI state
- Loading workspace on app start

#### IPC bridge

Responsible for:

- Safe communication between renderer and Electron main process
- Keeping PTY operations outside unsafe renderer code

## 7. Data Model

The most important design decision is to separate:

- Tree metadata
- Process runtime state

These are related, but not the same.

### 7.1 Session Node

Each tree item should have a persistent metadata record.

Suggested fields:

```ts
type SessionNode = {
  id: string;
  parentId: string | null;
  title: string;
  orderIndex: number;
  isCollapsed: boolean;
  shellPath: string;
  initialCwd: string;
  lastKnownCwd: string | null;
  createdAt: string;
  updatedAt: string;
};
```

Field meanings:

- `id`: stable unique identifier
- `parentId`: null for roots
- `title`: displayed title
- `orderIndex`: ordering among siblings
- `isCollapsed`: sidebar visual state
- `shellPath`: shell used to launch the session
- `initialCwd`: cwd used when the process was created
- `lastKnownCwd`: most recent known cwd
- `createdAt` / `updatedAt`: metadata timestamps

### 7.2 Runtime Session State

Runtime process information should be stored separately in memory.

Suggested fields:

```ts
type RuntimeSessionState = {
  sessionId: string;
  ptyPid: number | null;
  status: "starting" | "running" | "exited" | "error";
  exitCode: number | null;
  terminalBufferAttached: boolean;
};
```

Reason for separation:

- Metadata must survive app restart
- Runtime state does not need to survive restart in the same way

## 8. PTY Lifecycle

### 8.1 Creating a Session

When creating a session:

1. Create metadata record
2. Launch PTY using selected shell and cwd
3. Attach PTY output stream
4. Mark session as `running`
5. Render terminal in the main pane when selected

If PTY creation fails:

- Keep the metadata record only if you want the failed session visible for debugging
- Otherwise remove it and show a clear error

Recommended V1 behavior:

- Do not keep failed phantom sessions
- Show a message and abort creation cleanly

### 8.2 Viewing a Session

When a session is selected:

- If already running, attach terminal view to its data stream
- If exited and V1 supports reopen, show a `Relaunch` action

V1 should not create a new shell just because a user clicks an exited session unless that behavior is clearly labeled.

### 8.3 Exiting

When the shell exits:

- Mark runtime state as `exited`
- Preserve metadata record
- Show an exited state in the sidebar

This is useful because the user may want to inspect the session title or tree structure even after the process is gone.

### 8.4 Deleting a Session

Deleting a session means removing metadata from persistence.

Rules:

- Stop the PTY if still running
- Apply branch promotion if needed
- Remove metadata record
- Save updated tree state

## 9. Tracking Current Working Directory

This is one of the trickier parts of the app.

Problem:

- A PTY can be launched with an initial cwd
- But after launch, the shell can `cd` anywhere
- The app needs the latest cwd when spawning child sessions

### 9.1 Acceptable V1 Strategy

Use shell integration hooks where possible.

Idea:

- For supported shells, inject a small shell snippet that reports cwd changes to the host app
- Update `lastKnownCwd` whenever a report arrives

Examples by shell:

- zsh: use `precmd` / `chpwd`
- bash: use `PROMPT_COMMAND`
- fish: use shell event hooks

If shell integration is unavailable:

- Fall back to `initialCwd`

This is acceptable for V1 as long as it is documented.

### 9.2 UX Rule

When creating a child session:

- Prefer `lastKnownCwd`
- Else use `initialCwd`
- Else use app default cwd

The user should not be surprised by a child opening in a random location.

## 10. Persistence

### 10.1 What Should Be Saved

Persist the following:

- Session metadata
- Parent/child relationships
- Ordering among siblings
- Collapsed state
- Last selected session id
- Last known cwd if available

### 10.2 What Should Not Be Saved as If It Were Durable

Do not pretend that these survive app restart unless you actually implement them:

- Exact terminal buffer state
- Running shell process state
- Interactive program state inside the shell

If later versions add real persistence, it should be explicit.

### 10.3 Startup Flow

Recommended startup flow:

1. Load metadata records from SQLite
2. Rebuild in-memory tree
3. For each saved session, create a fresh shell process
4. Restore selection and collapsed state
5. If relaunch fails for one session, mark it errored and continue loading the rest

This startup behavior is robust because one bad shell launch should not block the whole workspace.

## 11. User Flows

### 11.1 New Root Session

1. User clicks `New Root Session`
2. App chooses shell and cwd
3. App creates PTY
4. App saves node as root
5. App selects the new session

### 11.2 New Child Session

1. User selects a node
2. User clicks `New Child Session`
3. App reads `lastKnownCwd` or fallback cwd
4. App creates PTY
5. App saves node with `parentId` set
6. App expands parent if needed
7. App selects child

### 11.3 Close Leaf Session

1. User closes a session with no children
2. App terminates PTY if still running
3. App removes node from persistence
4. App selects a nearby session

### 11.4 Close Parent Session

1. User closes a session with children
2. App shows confirmation
3. User selects `Close this session only and promote children`
4. App terminates PTY
5. App reparents children
6. App removes closed node
7. App saves updated tree

### 11.5 Restart App

1. App loads saved tree
2. App launches fresh shells
3. App restores expanded/collapsed state
4. App restores selection if possible

## 12. Error Handling

The app should fail clearly, not silently.

Important error cases:

- Shell executable missing
- PTY launch failure
- Invalid cwd
- SQLite open failure
- Corrupted tree data

Expected behavior:

- Show clear user-facing message
- Keep unaffected sessions working
- Avoid crashing the whole app unless startup is impossible

### 12.1 Invalid Tree Recovery

If persisted tree data is broken, for example:

- a node references a missing parent
- sibling order indexes conflict

Then recovery rules should be deterministic:

- Missing parent: convert node to root
- Duplicate order index: sort by creation time then reassign indexes
- Invalid selected session id: select first available root

Recovery logic should be tested because user trust depends on not losing the workspace.

## 13. Suggested Folder Structure

One clean way to structure the codebase:

```text
src/
  main/
    ipc/
    pty/
    persistence/
    windows/
    main.ts
  renderer/
    app/
    components/
    features/
      session-tree/
      terminal-view/
      workspace/
    styles/
    renderer.tsx
  shared/
    types/
    constants/
```

Guidance:

- `main/` owns PTY and database access
- `renderer/` owns UI only
- `shared/` owns shared types and IPC contracts

## 14. Testing Strategy

The app needs tests at three levels:

- Unit tests
- Integration tests
- Manual acceptance tests

This is important because terminal apps often look simple in the UI while hiding many lifecycle bugs.

## 15. Unit Tests

Unit tests should target logic that can be validated without launching a full desktop app.

### 15.1 Tree Reducer / Tree State Logic

Test cases:

- Create root session adds a root node
- Create child session attaches under selected parent
- Collapse toggles only the target node
- Reorder among siblings updates `orderIndex`
- Closing a leaf removes only that node
- Closing a parent promotes children correctly
- Deleting one branch does not affect unrelated branches
- Selecting a removed node falls back to a valid node

These tests matter because the tree is the product's main differentiator.

### 15.2 Persistence Serialization

Test cases:

- Session records serialize and deserialize correctly
- Parent/child relationships survive reload
- Collapsed state survives reload
- Selection state survives reload
- Invalid records trigger deterministic recovery behavior

### 15.3 Session Naming Logic

Test cases:

- Auto-generated names increment correctly
- Renamed sessions keep custom names
- Closing a session does not retroactively rename others

### 15.4 CWD Selection Logic

Test cases:

- Child uses `lastKnownCwd` when present
- Falls back to `initialCwd` if no `lastKnownCwd`
- Falls back to default cwd if neither is available
- Invalid cwd is rejected or repaired consistently

## 16. Integration Tests

Integration tests should validate behavior across multiple components together.

### 16.1 PTY Session Creation

Test cases:

- App can launch a shell PTY successfully
- PTY output reaches terminal consumer
- PTY exit updates runtime state
- Failed PTY launch produces error without corrupting tree state

### 16.2 IPC Contracts

Test cases:

- Renderer can request new root session
- Renderer can request new child session
- Renderer can request rename
- Renderer can request close
- Main process returns structured success/error responses

### 16.3 Persistence + Relaunch

Test cases:

- Save workspace, reload app state, verify tree shape
- Collapsed state restored on reload
- Selected session restored when valid
- Missing parent repaired into root during reload

### 16.4 Shell Integration for CWD Tracking

If shell hooks are implemented, test:

- cwd updates are received after `cd`
- malformed cwd messages are ignored safely
- lack of shell integration falls back gracefully

## 17. End-to-End / UI Tests

If the project later adds Playwright or another desktop automation layer, the most valuable end-to-end tests are:

- Create root session and type command
- Create child session and verify tree placement
- Collapse and expand branch
- Rename session from sidebar
- Close parent and promote children
- Restart app and verify restored tree structure

These tests should be fewer than unit tests because they are slower and more brittle.

## 18. Manual Acceptance Tests

These are important because terminal behavior can be difficult to fully automate.

### 18.1 Basic Session Flow

Manual test:

1. Launch app
2. Create one root session
3. Run `pwd`
4. Create a child session
5. Confirm child opens under the correct parent
6. Confirm child is interactive

Expected result:

- Both sessions are usable
- Tree matches the expected hierarchy

### 18.2 Collapse Behavior

Manual test:

1. Create one root with two children
2. Collapse the root
3. Wait a few seconds while a child runs a visible command
4. Expand the root

Expected result:

- Child sessions were hidden only visually
- Child processes remained alive

### 18.3 Close Parent with Promotion

Manual test:

1. Create one root
2. Create two children under it
3. Close the root
4. Confirm the promotion option

Expected result:

- Root disappears
- Former children become roots
- Their PTY sessions remain active

### 18.4 Workspace Restore

Manual test:

1. Create several roots and children
2. Rename some sessions
3. Collapse one branch
4. Quit app
5. Relaunch app

Expected result:

- Tree shape is restored
- Titles are restored
- Collapse state is restored
- Fresh shells are launched for restored sessions, if that is the chosen V1 behavior

### 18.5 Invalid CWD Fallback

Manual test:

1. Start a session
2. Change into a temporary directory
3. Remove that directory externally if possible
4. Create a child session

Expected result:

- App falls back to a safe default cwd
- App shows a clear error or warning if needed
- App does not crash

## 19. Release Criteria for MVP

The MVP should be considered ready only if all of the following are true:

- User can create and use multiple terminal sessions
- Tree relationships are visible and stable
- Child sessions open under the expected parent
- Collapse/expand works without affecting process execution
- Close behavior is predictable and non-destructive
- Workspace structure restores after relaunch
- Major failure cases produce understandable errors

If these are not true, the product is not yet solving the core problem reliably.

## 20. Risks and Hard Parts

These are the areas most likely to cause engineering trouble:

### 20.1 CWD Tracking

This is easy to underestimate.
It should be treated as a real feature, not a detail.

### 20.2 PTY Stability Across Platforms

Different operating systems and shells behave differently.
Even if V1 starts on one OS, the architecture should not assume identical PTY behavior everywhere.

### 20.3 Restore Expectations

Users may assume "restore workspace" means full process continuity.
The product must describe this precisely so users are not misled.

### 20.4 Tree Mutation Bugs

Reparenting, deletion, and reorder bugs can silently damage workspace structure.
This is why tree logic should be isolated and tested thoroughly.

## 21. Practical Build Order

The cleanest implementation order is:

1. Basic Electron shell
2. Single PTY-backed terminal
3. Multiple flat sessions
4. Tree sidebar with static sample data
5. Real tree-backed session creation
6. Rename, collapse, selection, close
7. Persistence
8. CWD tracking
9. Test hardening

Reason:

- First prove that PTY + terminal rendering works
- Then prove multi-session switching
- Then add tree semantics
- Then persistence
- Then harder shell integration details

## 22. Recommended First Milestone

A good first milestone is:

"A desktop app where I can create root and child terminal sessions, see them in a collapsible tree, switch between them, and quit/reopen the app with the tree structure preserved."

That milestone is narrow enough to build, but complete enough to validate the product idea.

## 23. Final Summary

This app should be treated as a terminal workspace manager with a tree-based mental model.

The key idea is not "more tabs."
The key idea is "visible session lineage."

If implemented well, the result should make multi-session terminal work feel:

- more organized
- easier to navigate
- less mentally expensive

The implementation should stay disciplined in V1:

- generic shell sessions only
- strong tree behavior
- clear close semantics
- honest restore behavior
- serious testing around tree logic and lifecycle handling

If those foundations are solid, more advanced features can be added later without corrupting the product's core simplicity.
