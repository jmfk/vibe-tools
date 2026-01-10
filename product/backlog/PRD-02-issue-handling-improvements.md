---
discussion_id: D_kwDOQzI0Lc4AjlrL
discussion_url: https://github.com/jmfk/vibe-tools/discussions/5
last_synced_at: '2026-01-10T17:22:07.589596'
sync_hash: 18443269ab898b94a5a32679dfb5d8bcca8e265641fbbc600b6bdc84127d5b34
---

# PRD-02: Issue Handling Improvements

**Project:** vibe-tools
**Feature:** Issue Management Enhancements (List, Search, Add)
**Status:** Implemented
**Owner:** Core Platform
**Last updated:** 2026-01-09

------

## 1. Purpose & Motivation

The current issue management system provides a solid foundation with local-first storage and GitHub sync. However, the discovery and creation workflows need improvement:
- **Discovery**: Users cannot easily list or search existing issues from the CLI without manual file exploration.
- **Creation**: The existing `investigate` command is powerful but heavy, requiring multiple interactive prompts and log analysis. A "lightweight" way to quickly add an issue from a single thought is needed.

------

## 2. Core Requirements

### 2.1. `vibe issue list` (and `vibe issue ls`)
A command to list local issues with basic filtering and search.

- **Listing**: Show a table or list of issues from `issues/backlog/` and `issues/history/`.
- **Filtering**:
    - `--status`: Filter by status (backlog, in_progress, blocked, done).
    - `--severity`: Filter by severity (low, medium, high, critical).
    - `--service`: Filter by service name.
- **Searching**: 
    - Positional argument or `--search` flag to filter by title or body content.
- **Display**:
    - Default to a concise table view (ID, Title, Status, Severity, Service).
    - Optional `--full` or `-v` for more detail.

### 2.2. `vibe issue add`
A lightweight command for rapid issue creation.

- **Prompt-based**: Accept a single string argument as a "prompt" to create an issue.
- **Auto-generation**: Use AI to derive the title, summary, and severity from the prompt if not explicitly provided.
- **CLI Options**:
    - `--title`: Explicitly set the title.
    - `--severity`: Explicitly set the severity.
    - `--service`: Explicitly set the service.
- **Behavior**:
    - Unlike `investigate`, it should NOT require log analysis or multiple prompts.
    - It should immediately save a valid `Issue` artifact to `issues/backlog/`.

------

## 3. Implementation Details

### 3.1. Data Layer (`vibe_tools/issues.py`)
- The existing `Issue` dataclass and `load_index`, `save_issue` functions will be reused.
- Add helper functions if necessary for efficient searching across all issues.

### 3.2. CLI Integration (`vibe_tools/commands/issue.py`)
- Register the new subcommands in the existing `issue` group.

### 3.3. Command: `list`
- Implementation in `vibe_tools/commands/issue_list.py` (or within `issue.py`).
- Use `click` options for filtering.
- Implement simple regex or substring matching for search.

### 3.4. Command: `add`
- Implementation in `vibe_tools/commands/issue_add.py` (or within `issue.py`).
- Integration with the LLM/Agent logic to populate the issue body from the short prompt.
- Use a simplified version of the PRD generation prompt or a dedicated `issue_add_prompt.txt`.

------

## 4. User Experience

### 4.1. `vibe issue list` Example
```bash
vibe issue list --status backlog --search "cache"
```
Output:
```
ID                   TITLE                                     STATUS    SEV.    SERVICE
ISSUE-2026-01-09-001  Service crashes on startup (cold cache)   backlog   high    api-gateway
```

### 4.2. `vibe issue add` Example
```bash
vibe issue add "The login button is misaligned on mobile safari" --service frontend
```
Output:
```
✅ Issue created: ISSUE-2026-01-09-002
Title: Login button misalignment on Mobile Safari
Location: issues/backlog/ISSUE-2026-01-09-002.md
```

------

## 5. Success Criteria
- Users can list issues without manual `ls issues/backlog/`.
- Search works across title and status.
- `vibe issue add` creates a complete, valid issue artifact from a single CLI command.