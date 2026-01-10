# Architecture Specification

## 1. Core Philosophy
The project follows a **CLI-First** philosophy. We prioritize terminal interactions and automated developer workflows. The goal is to maximize development velocity using AI-assisted tooling that operates directly on the codebase.

## 2. Tech Stack

### 2.1 Backend
- **Language**: Python 3.11
- **CLI**: Click (for a robust command-line interface)
- **AI Orchestration**: `dspy` for structured LLM interactions

### 2.2 AI & Tooling
- **Vibe CLI**: Unified command-line interface (`vibe`) for all developer workflows.
- **Prompts**: Version-controlled AI prompts in `prompts/`.

## 3. Project Structure
```text
/
├── vibe_tools/      # Core automation logic and CLI implementation
├── product/         # Markdown PRDs and high-level specifications
├── implementation/  # Machine-readable state, logs, and normalized PRDs
├── prompts/         # AI prompt templates
├── tests/           # Comprehensive test suite
├── docs/            # User and developer documentation
└── frontend/        # Frontend implementation (where applicable)
```

## 4. Development Lifecycle (8-Phase)
The core of the project's operation follows an 8-phase lifecycle, driven by the `vibe` CLI:

1.  **Normalize**: Convert high-level PRDs into machine-readable implementation plans.
2.  **Setup**: Initialize the project environment and configurations.
3.  **Deps**: Manage project dependencies.
4.  **Implement**: Execute the main implementation loop using AI agents.
5.  **Infra**: Provision and manage local or cloud infrastructure.
6.  **Testing**: Run test suites and improve coverage.
7.  **CICD**: Configure and run continuous integration and deployment pipelines.
8.  **Deploy**: Deploy the application to target environments (local or cloud).

## 5. Key Design Patterns
- **CLI-First Workflow**: All tasks are driven by the unified `vibe` command.
- **PRD-Driven Development**: Changes start with a PRD in `product/`, which is then normalized into `implementation/`.
- **Agentic Loops**: Uses `dspy` and custom agents (like Ralph) for iterative code generation and improvement.
- **Tiered Configuration**: Environment management via project-level `.vibe_config.json` and global `~/.vibe/config.json`.
