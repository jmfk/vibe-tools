---
discussion_id: D_kwDOQzI0Lc4AjlwH
discussion_url: https://github.com/jmfk/vibe-tools/discussions/71
last_synced_at: '2026-01-10T22:24:09.174372'
sync_hash: a5866fdaf779618c765476d0466873864573ca7a28386ae8ec4e4e9633f86e6b
---

# Architecture Specification

## 1. Core Philosophy
The project follows a **CLI-First** philosophy. We prioritize terminal interactions and automated developer workflows. The goal is to maximize development velocity using AI-assisted tooling that operates directly on the codebase.

## 2. Tech Stack

### 2.1 Backend
- **Language**: Python 3.11
- **CLI**: Click (for a robust command-line interface)
- **AI Orchestration**: `google-genai` for structured LLM interactions

### 2.2 AI & Tooling
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

## 4. Development Lifecycle (8-Phase)
The core of the project's operation follows an 8-phase lifecycle, driven by the `vibe` CLI:

1.  **Normalize**: `vibe normalize` - Convert high-level PRDs into machine-readable implementation plans.
2.  **Setup**: `vibe setup` - Initialize the project environment and reconcile architecture.
3.  **Deps**: `vibe deps` - Manage and install project dependencies.
4.  **Implement**: `vibe implement` - Execute the main implementation loop using AI agents.
5.  **Infra**: `vibe infra` - Provision and manage production infrastructure. (Optional: only needed if the project requires cloud deployment).
6.  **Testing**: `vibe testing` - Run test suites and improve coverage.
7.  **CICD**: `vibe cicd` - Configure and run continuous integration and deployment pipelines.
8.  **Deploy**: `vibe deploy` - Deploy the application to target environments.

## 5. Core Commands

### 5.1 Project Management
- `vibe architect`: Generate or update core specifications (architecture, infra, etc.). Note: `infrastructure.md` is optional.
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
- `vibe servers`: Manage local development servers via Docker.

## 6. Key Design Patterns
- **CLI-First Workflow**: All tasks are driven by the unified `vibe` command.
- **PRD-Driven Development**: Changes start with a PRD in `product/`, which is then normalized into `implementation/`.
- **Agentic Loops**: Uses `google-genai` and custom agents (like Ralph) for iterative code generation and improvement.
- **Tiered Configuration**: Environment management via project-level `.vibe_config.json` and global `~/.vibe/config.json`.