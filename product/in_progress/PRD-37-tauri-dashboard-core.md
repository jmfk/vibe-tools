# PRD-37: Tauri Dashboard Core

**Project:** vibe-tools
**Feature:** GUI Dashboard Core
**Status:** Draft
**Owner:** Core Platform
**Last updated:** 2026-01-13

------

## 1. Purpose & Motivation

The goal of this feature is to introduce a **Tauri-based desktop application** that provides a unified, graphical interface for the `vibe-tools` ecosystem. While the CLI remains the primary interface for automation and remote execution, the Dashboard offers a rich environment for visualization, interactive debugging, and multi-stream monitoring.

The system should:
- Provide a **multi-pane layout** for simultaneous monitoring of chat, documents, and logs.
- Support **real-time updates** from the filesystem and running processes.
- Maintain **local-first principles** by operating directly on the project files.
- Integrate with existing **AI agents** via a familiar chat interface.

------

## 2. Core Principles

1. **Native Performance**: Use Tauri for a lightweight, native experience with low memory footprint.
2. **FileSystem as Source of Truth**: The app reads/writes directly to the workspace, ensuring zero-sync overhead.
3. **Extensibility**: The UI should be component-based, allowing for new "cards" or "modules" (e.g., testing, billing).
4. **Real-time Stream**: Logs and terminal outputs must be streamed, not polled.
5. **Interactive Agent Loop**: Provide a rich UI for agent interactions beyond text (buttons, status indicators).

------

## 3. Layout & UI Structure

The dashboard will follow a modern, IDE-like layout:

### 3.1 Left Pane: Agent Chat Interface
- A dedicated area for interacting with **Architect**, **PM**, and other agents.
- Support for markdown rendering in messages.
- Command shortcuts and auto-completion.
- Status indicators for active agent processes.

### 3.2 Main Area: Dynamic Workspaces
- Tabbed interface to switch between:
    - **Explorer**: Browse PRDs, Specs, and Issues.
    - **Monitor**: View logs and terminal output.
    - **Runner**: Start and track command execution.
    - **Testing**: View and interact with test cards.

### 3.3 Right Sidebar (Collapsible): Meta-Information
- Project status summary (similar to `vibe status`).
- Active services status.
- Cost tracking overview.

------

## 4. Technical Stack

- **Framework**: Tauri (Rust backend).
- **Frontend**: React or Next.js with Tailwind CSS.
- **Communication**: Tauri Events and Commands for IPC.
- **Styling**: Dark-mode first, consistent with terminal aesthetics.
- **Markdown**: `react-markdown` with `remark-gfm` and `rehype-highlight`.

------

## 5. Security & Permissions

- The app requires broad filesystem access within the workspace.
- API keys (Google, Cursor) should be managed via `.env` or system keyring, accessible by the Rust backend.
- Command execution must be restricted to the workspace directory.

------

## 6. Success Criteria

- App starts in under 2 seconds.
- Filesystem changes in `product/` or `issues/` are reflected in the UI within 500ms.
- Smooth streaming of log files exceeding 10,000 lines.
- No interference with existing CLI workflows.

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-37
title: Tauri Dashboard Core
type: FEATURE
status: in_progress
group: null
depends_on: []
created_at: 2026-01-13
updated_at: '2026-01-14T17:43:01.617239'
owner: Core Platform
implementation_id: v01-480
implementation_yaml: v01-480_37_tauri_dashboard_core.yaml
discussion_id: null
last_synced_at: null
sync_hash: null
issue_number: null
```
</details>

<!-- vibe-id: PRD-37 -->
