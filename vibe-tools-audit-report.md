# Vibe Tools CLI Command Audit Report

## Executive Summary
This report provides a comprehensive audit of the `vibe-tools` CLI commands. The system is designed around a multi-phase development lifecycle (Phases 1-9) and supporting utilities. While the core functionality is robust, there are several naming redundancies, duplicate entry points, and placeholder commands that should be consolidated for a better user experience.

## Command Reference

### 1. Core Development Lifecycle (Phases 1-9)
These commands represent the primary workflow for building projects with `vibe-tools`.

| Command | Phase | Description | Status |
| :--- | :--- | :--- | :--- |
| `vibe architect` | 1 | Interactive architecture and infrastructure spec manager. | ✅ Working |
| `vibe prd` | - | Unified PRD and initiative management (list, plan, history). | ✅ Working |
| `vibe pm` | 2 | Interactive Product Manager for requirement and PRD management. | ✅ Working |
| `vibe setup` | 3 | Architecture reconciliation (SRD-architecture.md vs current). | ✅ Working |
| `vibe deps` | 4 | Installs Python and Frontend dependencies. | ✅ Working |
| `vibe implement` | 5 | Main implementation loop for features and PRDs. | ✅ Working |
| `vibe build` | - | Builds the app and verifies it starts. | ✅ Working |
| `vibe infra` | 6 | Infrastructure reconciliation for production/live-staging. | ✅ Working |
| `vibe testing` | 7 | Testing reconciliation loop. | ✅ Working |
| `vibe cicd` | - | CI/CD pipeline management. | ❌ Placeholder |
| `vibe deploy` | 8/9 | Final deployment trigger. | ⚠️ Skeleton only |

### 2. Infrastructure & Service Management
Commands for managing local development dependencies and global project configuration.

| Command | Description | Status |
| :--- | :--- | :--- |
| `vibe servers` | Manage local development servers via Docker. | ✅ Working |
| `vibe config` | Setup and configuration for APIs, Services, and Scaffolding. | ✅ Working |
| `vibe-setup` | Alias for `vibe config`. | ✅ Working |

### 3. Supporting Utilities
Tools for status reporting, cost tracking, and specialized developer tasks.

| Command | Description | Status |
| :--- | :--- | :--- |
| `vibe status` | Comprehensive system status report. | ✅ Working |
| `vibe cost` | Cost reporting and reconciliation. | ✅ Working |
| `vibe usage` | Usage and billing statistics. | ✅ Working |
| `vibe history` | View project history and previous PRDs. | ✅ Working |
| `vibe docs` | Documentation management. | ✅ Working |
| `vibe memory` | System memory management for agents. | ✅ Working |
| `vibe issue` | Local-first issue management group. | ✅ Working |
| `vibe investigate`| Guided investigation from logs. | ✅ Working |
| `vibe solve` | Resolve issues via agent-driven loop. | ✅ Working |
| `vibe kill` | Kill background agent processes. | ✅ Working |
| `vibe ps` | List active agent processes. | ✅ Working |
| `vibe billing-groups`| Manage billing groups for Cursor/LLM tracking. | ✅ Working |
| `vibe demo-data` | Manage demo data for staging environments. | ✅ Working |

## Redundancy & Conflict Analysis

### 1. The "Setup" Confusion
The system has three related but overlapping concepts:
- **`vibe setup`**: Specifically for Phase 3 (Architecture reconciliation).
- **`vibe config`**: For global setup (LLM keys, services, scaffolding).
- **`vibe-setup`**: A standalone entry point that is a direct alias for `vibe config`.
- **Action**: Rename `vibe setup` to `vibe reconcile-arch` or similar, and consolidate `vibe-setup` into `vibe config`.

### 2. Duplicate Command Registration
- `vibe investigate` and `vibe solve` are available as top-level commands AND as subcommands of `vibe issue`.
- **Action**: Keep them as subcommands of `vibe issue` and remove the top-level duplicates to clean up the main help menu.

### 3. Doc vs. Code Discrepancy (`vibe-servers`)
- Documentation frequently refers to `vibe-servers` (with a hyphen) as a standalone command.
- The implementation only provides `vibe servers` (subcommand).
- **Action**: Update documentation to use `vibe servers` and potentially add a `vibe-servers` entry point for backward compatibility/ease of use.

### 4. Overlapping Dependency Management
- `vibe deps` and `vibe config deps` both call the exact same `install_deps` logic.
- **Action**: Remove `vibe config deps`.

## Non-Working & Placeholder Commands
The following commands appear in the CLI's internal ordering list but are not actually registered or implemented:
- `vibe run`
- `vibe start`
- `vibe run-status`
- `vibe cicd`

## Actionable Recommendations

1. **Unify Configuration**: Consolidate `vibe config`, `vibe-setup`, and `vibe setup` names to prevent confusion.
2. **Clean Main CLI**: Remove redundant top-level aliases (`solve`, `investigate`, `billing-groups`) and group them under their respective parent commands.
3. **Remove Placeholders**: Remove `run`, `start`, `run-status`, and `cicd` from the help menu/ordering until implemented.
4. **Update Docs**: Sync documentation with the actual CLI structure (especially regarding `vibe-servers`).
5. **Implement Deploy**: Flesh out the `vibe deploy` skeleton or mark it as a future feature.
