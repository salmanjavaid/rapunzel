import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import './styles.css';

const state = {
  ui: null,
  selectedSessionId: null,
  syncing: false,
  syncPending: false,
  syncPendingReset: false,
  contextMenuActionPending: false,
  resizeTimer: null,
  contextMenuTargetId: null,
  terminals: new Map(),
};

const elements = {};

// ------------------------------------------------------------------
// Push handlers: Python calls these directly via evaluate_js
// (same pattern as VS Code's PTY onData → xterm.write)
// ------------------------------------------------------------------

window.__rapunzelPtyOutput = function (sessionId, data) {
  const entry = terminalEntry(sessionId);
  if (!entry) return;

  if (!entry.hydrated) {
    entry.pendingPush = (entry.pendingPush || '') + data;
    return;
  }

  entry.term.write(data);
};


window.__rapunzelPtyExit = function (sessionId, exitCode) {
  const entry = terminalEntry(sessionId);
  if (entry) {
    entry.term.write(`\r\n[process exited with code ${exitCode}]\r\n`);
  }
};

window.addEventListener('pywebviewready', () => {
  bindElements();
  bindActions();
  new ResizeObserver(() => scheduleResize()).observe(elements.terminalCard);
  window.addEventListener('resize', scheduleResize);
  // Tell Python that push handlers are ready
  window.pywebview.api.signal_ready();
  syncUi(true);
  // Tree/selection sync only — output comes via push, not polling
  window.setInterval(() => syncUi(false), 1000);
});

function bindElements() {
  elements.tree = document.querySelector('#tree');
  elements.activeTitle = document.querySelector('#active-title');
  elements.activeMeta = document.querySelector('#active-meta');
  elements.terminalMount = document.querySelector('#terminal-mount');
  elements.terminalCard = document.querySelector('#terminal-card');
  elements.newRoot = document.querySelector('#new-root');
  elements.newChild = document.querySelector('#new-child');
  elements.rename = document.querySelector('#rename');
  elements.moveUp = document.querySelector('#move-up');
  elements.moveDown = document.querySelector('#move-down');
  elements.toggleCollapse = document.querySelector('#toggle-collapse');
  elements.close = document.querySelector('#close');
  const contextMenuElements = createContextMenu();
  elements.contextMenuOverlay = contextMenuElements.overlay;
  elements.contextMenu = contextMenuElements.menu;
}

function bindActions() {
  elements.newRoot.addEventListener('click', async () => {
    const ui = await window.pywebview.api.create_root();
    await applyUiState(ui, true);
  });

  elements.newChild.addEventListener('click', async () => {
    if (!state.selectedSessionId) return;
    const ui = await window.pywebview.api.create_child();
    await applyUiState(ui, true);
  });

  elements.rename.addEventListener('click', renameSelected);
  elements.moveUp.addEventListener('click', () => moveSelected('up'));
  elements.moveDown.addEventListener('click', () => moveSelected('down'));
  elements.toggleCollapse.addEventListener('click', toggleSelectedCollapsed);
  elements.close.addEventListener('click', closeSelected);
  elements.tree.addEventListener('contextmenu', handleTreeContextMenu);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      hideContextMenu();
    }
  });
  window.addEventListener('resize', hideContextMenu);
  elements.tree.addEventListener('scroll', hideContextMenu, { passive: true });
  elements.contextMenuOverlay.addEventListener('pointerdown', (event) => {
    if (event.target.closest('.tree-context-menu')) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    hideContextMenu();
  });
  elements.contextMenu.addEventListener('pointerdown', (event) => {
    const actionNode = event.target.closest('.tree-context-menu-item');
    if (actionNode) {
      handleContextMenuAction(event);
      return;
    }

    event.preventDefault();
    event.stopPropagation();
  });
  elements.contextMenu.addEventListener('click', handleContextMenuAction);
  elements.contextMenu.addEventListener('contextmenu', (event) => {
    event.preventDefault();
    event.stopPropagation();
  });
}

async function renameSelected() {
  const selected = selectedNode();
  if (!selected) return;

  const title = window.prompt('Branch name:', selected.title);
  if (title === null) return;

  const ui = await window.pywebview.api.rename_session(selected.id, title);
  await applyUiState(ui, false);
}

async function moveSelected(direction) {
  if (!state.selectedSessionId) return;
  const ui = await window.pywebview.api.move_session(state.selectedSessionId, direction);
  await applyUiState(ui, false);
}

async function toggleSelectedCollapsed() {
  if (!state.selectedSessionId) return;
  const ui = await window.pywebview.api.toggle_collapsed(state.selectedSessionId);
  await applyUiState(ui, false);
}

async function closeSelected() {
  if (!state.selectedSessionId) return;
  const ui = await window.pywebview.api.close_session(state.selectedSessionId);
  await applyUiState(ui, true);
}

async function closeSession(sessionId) {
  if (!sessionId) return;
  const ui = await window.pywebview.api.close_session(sessionId);
  await applyUiState(ui, true);
}

async function closeBranch(sessionId) {
  if (!sessionId) return;
  const ui = await window.pywebview.api.close_branch(sessionId);
  await applyUiState(ui, true);
}

async function selectSession(sessionId) {
  hideContextMenu();
  const ui = await window.pywebview.api.select_session(sessionId);
  await applyUiState(ui, true);
}

async function sendInput(data) {
  if (!state.selectedSessionId) return;
  await window.pywebview.api.send_input(state.selectedSessionId, data);
}

async function scheduleResize() {
  window.clearTimeout(state.resizeTimer);
  state.resizeTimer = window.setTimeout(async () => {
    await fitAndResizeNow();
  }, 60);
}

async function fitAndResizeNow() {
  const entry = selectedTerminalEntry();
  if (!entry) {
    return;
  }

  const prevRows = entry.term.rows;
  const prevCols = entry.term.cols;
  entry.fitAddon.fit();

  if (entry.term.rows !== prevRows || entry.term.cols !== prevCols || !entry.sizeReported) {
    entry.sizeReported = true;
    await window.pywebview.api.resize_session(
      state.selectedSessionId,
      entry.term.rows,
      entry.term.cols,
    );
  }
}

// pollEvents removed — output is now pushed directly from Python via
// window.__rapunzelPtyOutput / window.__rapunzelPtyExit (VS Code pattern)

async function syncUi(resetTerminal) {
  if (state.syncing) {
    state.syncPending = true;
    state.syncPendingReset = state.syncPendingReset || resetTerminal;
    return;
  }

  state.syncing = true;

  try {
    const ui = await window.pywebview.api.get_ui_state();
    await applyUiState(ui, resetTerminal);
  } finally {
    state.syncing = false;

    if (state.syncPending) {
      const pendingReset = state.syncPendingReset;
      state.syncPending = false;
      state.syncPendingReset = false;
      window.queueMicrotask(() => {
        syncUi(pendingReset);
      });
    }
  }
}

async function applyUiState(ui, resetTerminal) {
  const selectedChanged = ui.selected_session_id !== state.selectedSessionId;

  state.ui = ui;
  state.selectedSessionId = ui.selected_session_id;
  pruneTerminalEntries(ui.tree);

  renderTree(ui.tree);
  renderHeader(ui.selected);
  renderActions(ui.selected);

  if (resetTerminal || selectedChanged) {
    await hydrateSelectedTerminal();
    return;
  }

  await showSelectedTerminal();
}

async function hydrateSelectedTerminal() {
  if (!state.selectedSessionId) {
    hideAllTerminalEntries();
    return;
  }

  const entry = ensureTerminalEntry(state.selectedSessionId);
  showTerminalEntry(state.selectedSessionId);
  entry.term.reset();
  entry.term.clear();
  entry.hydrated = false;
  // Discard any push data that arrived before reset — the snapshot
  // fetched below will already include it, so replaying pendingPush
  // would duplicate that output.
  entry.pendingPush = '';
  await fitAndResizeNow();

  const snapshot = await window.pywebview.api.get_session_snapshot(state.selectedSessionId);
  // Discard push data again — anything that arrived between the reset
  // above and the snapshot fetch is already inside the rendered buffer
  // (session_snapshot drains queued PTY output before reading it).
  entry.pendingPush = '';
  if (snapshot) {
    await writeToTerminal(entry.term, snapshot);
  }
  entry.term.scrollToBottom();
  entry.hydrated = true;

  // Only flush output that arrived AFTER the transcript was captured
  if (entry.pendingPush) {
    entry.term.write(entry.pendingPush);
    entry.pendingPush = '';
  }
}

function writeToTerminal(term, data) {
  return new Promise((resolve) => {
    term.write(data, resolve);
  });
}

function renderHeader(selected) {
  if (!selected) {
    elements.activeTitle.textContent = 'No branch selected';
    elements.activeMeta.textContent = 'Create a root branch to start a new workspace thread.';
    return;
  }

  elements.activeTitle.textContent = selected.title;
  const cwd = selected.cwd || selected.initial_cwd;
  elements.activeMeta.textContent = `${selected.status}  •  ${cwd}`;
}

function renderActions(selected) {
  const hasSelection = Boolean(selected);
  const selectedTreeNode = hasSelection ? selectedNode() : null;
  elements.newChild.disabled = !hasSelection;
  elements.rename.disabled = !hasSelection;
  elements.moveUp.disabled = !canMove(selected, 'up');
  elements.moveDown.disabled = !canMove(selected, 'down');
  elements.close.disabled = !hasSelection;
  elements.toggleCollapse.disabled = !selectedTreeNode || !selectedTreeNode.children?.length;
  elements.toggleCollapse.textContent = selected && selected.is_collapsed ? 'Expand' : 'Collapse';
}

function renderTree(nodes) {
  elements.tree.innerHTML = '';
  const fragment = document.createDocumentFragment();
  fragment.appendChild(renderBranchList(nodes));

  const newRootRow = document.createElement('button');
  newRootRow.className = 'new-root-row';
  newRootRow.textContent = '+  New Root';
  newRootRow.addEventListener('click', async () => {
    const ui = await window.pywebview.api.create_root();
    await applyUiState(ui, true);
  });
  fragment.appendChild(newRootRow);

  elements.tree.appendChild(fragment);

  if (elements.contextMenu.hidden) {
    return;
  }

  if (state.contextMenuTargetId) {
    const targetNode = findNode(nodes, state.contextMenuTargetId);
    if (!targetNode) {
      hideContextMenu();
      return;
    }

    renderContextMenu(targetNode);
    return;
  }

  renderContextMenu(null);
}

function renderBranchList(nodes) {
  const list = document.createElement('ul');
  list.className = 'branch-list';

  for (const node of nodes) {
    const item = document.createElement('li');
    item.className = 'branch-item';

    const row = document.createElement('div');
    row.className = `branch-row${node.id === state.selectedSessionId ? ' is-selected' : ''}`;
    row.dataset.sessionId = node.id;

    const toggle = document.createElement('button');
    toggle.className = 'branch-toggle';
    toggle.textContent = node.children.length ? (node.is_collapsed ? '▸' : '▾') : '';
    toggle.disabled = node.children.length === 0;
    toggle.addEventListener('click', async (event) => {
      event.stopPropagation();
      const ui = await window.pywebview.api.toggle_collapsed(node.id);
      await applyUiState(ui, false);
    });

    const label = document.createElement('div');
    label.className = 'branch-label';
    label.tabIndex = 0;
    label.setAttribute('role', 'button');
    label.addEventListener('click', () => selectSession(node.id));
    label.addEventListener('dblclick', renameSelected);
    label.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        selectSession(node.id);
      }
    });

    const title = document.createElement('span');
    title.className = 'branch-title';
    title.textContent = node.title;

    const status = document.createElement('span');
    status.className = 'branch-status';
    status.textContent = node.status;

    label.append(title, status);
    row.append(toggle, label);
    item.appendChild(row);

    if (node.children.length && !node.is_collapsed) {
      item.appendChild(renderBranchList(node.children));
    }

    list.appendChild(item);
  }

  return list;
}

function selectedNode() {
  return findNode(state.ui?.tree || [], state.selectedSessionId);
}

function createTerminal() {
  return new Terminal({
    allowTransparency: false,
    convertEol: false,
    cursorInactiveStyle: 'outline',
    cursorBlink: true,
    fontFamily: '"SF Mono", "JetBrains Mono", Menlo, Monaco, "Courier New", monospace',
    fontSize: 14,
    lineHeight: 1.25,
    minimumContrastRatio: 1,
    scrollback: 10000,
    theme: {
      background: '#05070b',
      foreground: '#f5f7ff',
      cursor: '#d8e3ff',
      selectionBackground: 'rgba(103, 132, 255, 0.28)',
    },
  });
}

function terminalEntry(sessionId) {
  return state.terminals.get(sessionId) || null;
}

function selectedTerminalEntry() {
  return terminalEntry(state.selectedSessionId);
}

function ensureTerminalEntry(sessionId) {
  let entry = terminalEntry(sessionId);
  if (entry) {
    return entry;
  }

  const mount = document.createElement('div');
  mount.className = 'terminal-pane';
  mount.hidden = true;
  elements.terminalMount.appendChild(mount);

  const fitAddon = new FitAddon();
  const term = createTerminal();
  term.loadAddon(fitAddon);
  term.open(mount);
  term.onData((data) => {
    if (sessionId === state.selectedSessionId) {
      sendInput(data);
    }
  });

  entry = {
    fitAddon,
    hydrated: false,
    mount,
    term,
  };
  state.terminals.set(sessionId, entry);
  return entry;
}

function hideAllTerminalEntries() {
  for (const entry of state.terminals.values()) {
    entry.mount.hidden = true;
  }
}

function showTerminalEntry(sessionId) {
  hideAllTerminalEntries();
  const entry = ensureTerminalEntry(sessionId);
  entry.mount.hidden = false;
}

async function showSelectedTerminal() {
  if (!state.selectedSessionId) {
    hideAllTerminalEntries();
    return;
  }

  const entry = ensureTerminalEntry(state.selectedSessionId);
  showTerminalEntry(state.selectedSessionId);
  await fitAndResizeNow();

  if (!entry.hydrated) {
    await hydrateSelectedTerminal();
  }
}

function pruneTerminalEntries(nodes) {
  const activeIds = new Set(flattenTreeIds(nodes));
  for (const [sessionId, entry] of state.terminals.entries()) {
    if (activeIds.has(sessionId)) {
      continue;
    }

    entry.term.dispose();
    entry.mount.remove();
    state.terminals.delete(sessionId);
  }
}

function flattenTreeIds(nodes) {
  const ids = [];
  for (const node of nodes) {
    ids.push(node.id);
    ids.push(...flattenTreeIds(node.children || []));
  }
  return ids;
}

function findNode(nodes, sessionId) {
  for (const node of nodes) {
    if (node.id === sessionId) {
      return node;
    }

    const child = findNode(node.children || [], sessionId);
    if (child) {
      return child;
    }
  }

  return null;
}

function createContextMenu() {
  const overlay = document.createElement('div');
  overlay.className = 'tree-context-menu-overlay';
  overlay.hidden = true;
  overlay.tabIndex = -1;

  const menu = document.createElement('div');
  menu.className = 'tree-context-menu';
  menu.hidden = true;
  menu.tabIndex = -1;
  overlay.appendChild(menu);
  document.body.appendChild(overlay);
  return { overlay, menu };
}

async function openContextMenuForSession(event, sessionId) {
  event.preventDefault();
  event.stopPropagation();

  state.contextMenuTargetId = sessionId;
  const targetNode = sessionId ? findNode(state.ui?.tree || [], sessionId) : null;
  renderContextMenu(targetNode);
  showContextMenu(event.clientX, event.clientY);
}

function handleTreeContextMenu(event) {
  const row = event.target.closest('.branch-row');
  if (row) {
    openContextMenuForSession(event, row.dataset.sessionId || null);
    return;
  }

  event.preventDefault();
  state.contextMenuTargetId = null;
  renderContextMenu(null);
  showContextMenu(event.clientX, event.clientY);
}

function renderContextMenu(targetNode) {
  const items = [
    { action: 'new-root', label: 'New Root', disabled: false },
    { action: 'new-child', label: 'New Child', disabled: !targetNode },
    { type: 'separator' },
    { action: 'rename', label: 'Rename', disabled: !targetNode },
    { action: 'move-up', label: 'Move Up', disabled: !canMove(targetNode, 'up') },
    { action: 'move-down', label: 'Move Down', disabled: !canMove(targetNode, 'down') },
    {
      action: 'toggle-collapse',
      label: targetNode?.is_collapsed ? 'Expand Branch' : 'Collapse Branch',
      disabled: !targetNode || !targetNode.children?.length,
    },
    { type: 'separator' },
    { action: 'close-tab', label: 'Close Tab', disabled: !targetNode },
    { action: 'close-branch', label: 'Close Branch', disabled: !targetNode },
  ];

  elements.contextMenu.replaceChildren();

  for (const item of items) {
    if (item.type === 'separator') {
      const separator = document.createElement('div');
      separator.className = 'tree-context-menu-separator';
      elements.contextMenu.appendChild(separator);
      continue;
    }

    const menuItem = document.createElement('button');
    menuItem.type = 'button';
    menuItem.className = `tree-context-menu-item${item.disabled ? ' is-disabled' : ''}`;
    menuItem.dataset.action = item.action;
    menuItem.setAttribute('role', 'menuitem');
    menuItem.disabled = item.disabled;
    menuItem.textContent = item.label;
    elements.contextMenu.appendChild(menuItem);
  }
}

function showContextMenu(x, y) {
  elements.contextMenuOverlay.hidden = false;
  elements.contextMenu.hidden = false;

  const { innerWidth, innerHeight } = window;
  const menuRect = elements.contextMenu.getBoundingClientRect();
  const left = Math.min(x, innerWidth - menuRect.width - 12);
  const top = Math.min(y, innerHeight - menuRect.height - 12);

  elements.contextMenu.style.left = `${Math.max(12, left)}px`;
  elements.contextMenu.style.top = `${Math.max(12, top)}px`;

  window.requestAnimationFrame(() => {
    if (elements.contextMenu.hidden) {
      return;
    }

    elements.contextMenu.focus({ preventScroll: true });
    const firstEnabledItem = elements.contextMenu.querySelector('.tree-context-menu-item:not(:disabled)');
    firstEnabledItem?.focus({ preventScroll: true });
  });
}

function hideContextMenu() {
  state.contextMenuTargetId = null;
  state.contextMenuActionPending = false;
  if (!elements.contextMenu) {
    return;
  }

  elements.contextMenuOverlay.hidden = true;
  elements.contextMenu.hidden = true;
}

async function handleContextMenuAction(event) {
  const actionNode = event.target.closest('.tree-context-menu-item');
  if (!actionNode || actionNode.disabled || actionNode.classList.contains('is-disabled')) {
    return;
  }

  const action = actionNode.dataset.action;
  if (!action || state.contextMenuActionPending) {
    return;
  }

  event.preventDefault();
  event.stopPropagation();
  state.contextMenuActionPending = true;

  const sessionId = state.contextMenuTargetId;
  hideContextMenu();

  if (action === 'new-root') {
    const ui = await window.pywebview.api.create_root();
    await applyUiState(ui, true);
    return;
  }

  if (!sessionId) {
    return;
  }

  if (action === 'new-child') {
    const ui = await window.pywebview.api.create_child_under(sessionId);
    await applyUiState(ui, true);
    return;
  }

  if (action === 'rename') {
    const node = findNode(state.ui?.tree || [], sessionId);
    if (!node) {
      return;
    }

    const title = window.prompt('Branch name:', node.title);
    if (title === null) {
      return;
    }

    const ui = await window.pywebview.api.rename_session(sessionId, title);
    await applyUiState(ui, false);
    return;
  }

  if (action === 'move-up' || action === 'move-down') {
    const ui = await window.pywebview.api.move_session(sessionId, action === 'move-up' ? 'up' : 'down');
    await applyUiState(ui, false);
    return;
  }

  if (action === 'toggle-collapse') {
    const ui = await window.pywebview.api.toggle_collapsed(sessionId);
    await applyUiState(ui, false);
    return;
  }

  if (action === 'close-tab') {
    await closeSession(sessionId);
    return;
  }

  if (action === 'close-branch') {
    await closeBranch(sessionId);
  }
}

function canMove(node, direction) {
  if (!node) {
    return false;
  }

  const siblings = siblingNodes(node.id);
  const index = siblings.findIndex((candidate) => candidate.id === node.id);
  if (index === -1) {
    return false;
  }

  if (direction === 'up') {
    return index > 0;
  }

  return index < siblings.length - 1;
}

function siblingNodes(sessionId) {
  const node = findNode(state.ui?.tree || [], sessionId);
  if (!node) {
    return [];
  }

  if (!node.parent_id) {
    return state.ui?.tree || [];
  }

  const parent = findNode(state.ui?.tree || [], node.parent_id);
  return parent?.children || [];
}
