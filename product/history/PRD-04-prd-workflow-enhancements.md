# PRD-04: PRD Workflow Enhancements: Inbox, Backlog, and History

## Problem
Currently, PRDs are stored in a single folder (`implementation/prds/`) and their status (implemented or not) is tracked in a monolithic `state.json` file. This makes it hard to manage a growing list of PRDs, see what's planned, and organize suggestions. There is no native support for "triaging" new ideas or "parking" dismissed ones.

## Goals
*   Establish a folder-based PRD status management system.
*   Provide clear separation between new suggestions (`inbox`), planned work (`backlog`), completed work (`history`), and dismissed ideas (`trash`).
*   Enable easy migration from the current system.
*   Provide intuitive commands for viewing and managing PRD status.
*   Allow editing PRDs in preferred external editors.

## Proposed Changes

### 1. New Directory Structure
The primary location for PRDs will change from `implementation/prds/` to `product/`.
Within `product/`, the following subdirectories will exist:
*   `inbox/`: For new, un-triaged PRDs or suggestions.
*   `backlog/`: For PRDs planned for implementation. The implementation loop will process these in alphabetical order (supporting numeric prefixes like `01_...`).
*   `history/`: For successfully implemented PRDs.
*   `trash/`: For dismissed or irrelevant PRDs.

### 2. Migration Command
A new command `vibe migrate` will be introduced to transition existing projects to this structure.
*   **Behavior**:
    *   Creates the `product/{inbox,backlog,history,trash}` directories.
    *   Reads `implementation/state.json` to identify `completed_prds` and moves corresponding files from `implementation/prds/` to `product/history/`.
    *   Moves all other PRDs from `implementation/prds/` to `product/backlog/`.
    *   If `vibe-tools-prds/` exists (legacy), it should also be considered during migration.
*   **Idempotency**: The command should be safe to run multiple times. It should skip files already in the target directories.

### 3. Management and Viewing Commands
The `view implement` command (alias `vibe i`) will be the hub for PRD management.

*   `vibe i [all|inbox|backlog|history|trash]`:
    *   Lists PRDs in the specified folder (defaults to `backlog` if no subcommand is provided).
    *   **Paging**: Display items in batches of 10.
    *   **Search**: Accepts an optional search term to filter results by filename.
*   `vibe implement move <id> <target_folder>`:
    *   Moves a PRD (identified by ID or partial name) from its current folder to the target folder.
    *   Supported targets: `inbox`, `backlog`, `history`, `trash`.
*   `vibe implement dismiss <id>`:
    *   Shortcut for `vibe implement move <id> trash`.
*   `vibe implement edit <id>`:
    *   Opens the specified PRD in the configured editor.

### 4. Configuration
A new configuration option `editor` will be added to `vibe_tools` configuration (`config.json`).
*   **Options**: `cursor`, `typora`, `code`, `vim`, etc.
*   **Usage**: When `vibe implement edit` is called, it spawns the configured editor process.

### 5. Implementation Loop Updates
The existing `vibe implement` loop will be updated to:
*   Look for machine-readable PRDs in `product/backlog/`.
*   Upon successful implementation of a PRD, move the file from `backlog/` to `history/`.

## Success Criteria
*   `vibe migrate` successfully reorganizes existing project PRDs.
*   `vibe i` provides a clean interface for exploring PRDs with search and paging.
*   Users can move PRDs between statuses using CLI commands.
*   `vibe implement` works seamlessly with the new folder structure.
*   `vibe implement edit` correctly opens the editor.

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-04
title: 'PRD-04: PRD Workflow Enhancements: Inbox, Backlog, and History'
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:37:25.057377'
updated_at: '2026-01-13T20:07:27.768675'
discussion_id: null
discussion_url: https://github.com/jmfk/vibe-tools/discussions/3
last_synced_at: null
sync_hash: null
issue_number: null
```
</details>

<!-- vibe-id: PRD-04 -->
