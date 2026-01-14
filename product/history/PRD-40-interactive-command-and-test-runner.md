# PRD-40: Interactive Command and Test Runner

**Project:** vibe-tools
**Feature:** Command Execution & Testing
**Status:** Draft
**Owner:** Core Platform
**Last updated:** 2026-01-13

------

## 1. Purpose & Motivation

This feature bridges the gap between static visualization and active execution. It allows users to trigger `vibe` commands and run interactive tests directly from the Dashboard, with dedicated UI for monitoring progress and making decisions.

------

## 2. Core Features

### 2.1 Command Execution Engine
- UI to trigger predefined `vibe` commands:
    - `vibe architect`
    - `vibe pm`
    - `vibe test`
    - `vibe implement`
- Parameter inputs for commands (e.g., branch name, PRD ID).
- Real-time process monitoring (Running, Stopped, Failed).

### 2.2 Interactive Testing Cards
- Load test scripts (Markdown format with specific test steps).
- Display tests as **Interactive Cards**:
    - Title and description.
    - List of steps.
    - Status indicator (Pending, In Progress, Passed, Failed).
- **Human-in-the-Loop**: Ability to manually mark steps as completed or provide feedback for agent-driven tests.
- Visual summary of test suite progress.

### 2.3 Process Management
- Stop/Kill running commands.
- View resource usage (if available).
- Automatic log connection (links command execution to its corresponding log stream).

------

## 3. UI Components

- **Command Launcher**: Grid or list of available actions.
- **Test Board**: Kanban or list view of test cards.
- **Card Detail**: Expanded view of a test script with step-by-step progress tracking.

------

## 4. Integration

- Integrates with `vibe_tools/utils.py`'s `run_command` and `run_agent` logic.
- Connects to `implementation/testing.yaml` for test definitions.

------

## 5. Success Criteria

- Ability to start and stop a complex `vibe architect` session from the UI.
- Intuitive interface for interacting with manual test steps.
- Clear visibility into the status of all running background tasks.

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-40
title: Interactive Command and Test Runner
type: FEATURE
status: done
group: null
depends_on:
- PRD-39
created_at: 2026-01-13
updated_at: '2026-01-14T20:01:29.833495'
owner: Core Platform
implementation_id: v01-460
implementation_yaml: v01-460_40_interactive_command_and_test_runner.yaml
discussion_id: null
last_synced_at: null
sync_hash: null
issue_number: null
impl_code_ready: true
impl_tests_passed: true
impl_review_passed: true
```
</details>

<!-- vibe-id: PRD-40 -->
