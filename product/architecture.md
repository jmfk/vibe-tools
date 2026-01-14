---
discussion_id: D_kwDOQzI0Lc4AjlwH
discussion_url: https://github.com/jmfk/vibe-tools/discussions/71
last_synced_at: '2026-01-10T22:24:09.174372'
sync_hash: a5866fdaf779618c765476d0466873864573ca7a28386ae8ec4e4e9633f86e6b
---

# Architecture Specification

## 1. Core Philosophy
The project follows a **CLI-First** philosophy. We prioritize terminal interactions and automated developer workflows. The goal is to maximize development velocity using AI-assisted tooling that operates directly on the codebase. Small change.

## 2. Tech Stack

### 2.1 Backend (CLI & Core Logic)
- **Language**: Python 3.11
- **CLI Framework**: Click
- **AI Orchestration**: `google-genai` for structured LLM interactions
- **Distribution**: `pipx` for global CLI access

### 2.2 Desktop GUI
- **Framework**: Tauri (Rust + Frontend)
- **Frontend**: React/TypeScript
- **Interactions**: Calls Python CLI functions/logic via Tauri sidecars or command execution.
- **Testing**: Dual-test approach using **Vitest** for the React frontend and **Cargo test** for the Rust backend commands.

### 2.3 AI & Tooling
- **Vibe CLI**: Unified command-line interface (`vibe`) for all developer workflows.
- **Prompts**: Version-controlled AI prompts in `prompts/`.

## 3. Project Structure
```text
/
├── vibe_tools/      # Core automation logic and CLI implementation
├── product/         # Markdown PRDs and high-level specifications
├── implementation/  # Machine-readable state, logs, and normalized PRDs
├── issues/          # Local-first issue tracking and management
├── prompts/         # AI prompt templates
├── tests/           # Comprehensive test suite
├── docs/            # User and developer documentation
└── frontend/        # Frontend implementation (where applicable)
```

## 4. Development Lifecycle (Core Phases)
The project's operation follows a set of core phases, driven by the `vibe` CLI and the Desktop App:

1.  **Normalize**: `vibe normalize` - Convert high-level PRDs into machine-readable implementation plans.
2.  **Setup**: `vibe setup` - Initialize the project environment and reconcile architecture.
3.  **Deps**: `vibe deps` - Manage and install project dependencies (Python & Node/Rust).
4.  **Implement**: `vibe implement` - Execute the main implementation loop using AI agents.
5.  **Testing**: `vibe testing` - Run test suites and improve coverage.

## 5. Core Commands

### 5.1 Project Management
- `vibe architect`: Generate or update core specifications (architecture, etc.).
- `vibe pm`: Interactive session for managing PRDs and project backlog.
- `vibe status`: Comprehensive report of project progress and system health.
- `vibe sync`: Synchronize local issues and PRDs with GitHub.
- `vibe init`: Initialize a new vibe-tools project structure.

### 5.2 Development Support
- `vibe issue`: Local-first issue management (add, list, close, investigate, solve).
- `vibe history`: View the development history and completed PRDs.
- `vibe memory`: Access and manage the project's long-term memory.
- `vibe cost`: Report estimated LLM and infrastructure costs.
- `vibe monitor`: Real-time monitoring of active agents and processes.
- `vibe config`: Configure API keys and global service settings.

## 6. Key Design Patterns
- **CLI-First Workflow**: All tasks are driven by the unified `vibe` command.
- **PRD-Driven Development**: Changes start with a PRD in `product/`, which is then normalized into `implementation/`.
- **Agentic Loops**: Uses `google-genai` and custom agents (like Ralph) for iterative code generation and improvement.
- **Tiered Configuration**: Environment management via project-level `.vibe_config.json` and global `~/.vibe/config.json`.