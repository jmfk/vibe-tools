# Architecture Specification (Desired)

## 1. Core Philosophy
The project follows a **CLI-First** philosophy. We prioritize terminal interactions and automated developer workflows. The goal is to maximize development velocity using AI-assisted tooling that operates directly on the codebase.

## 2. Tech Stack

### 2.1 Backend
- **Language**: Python 3.9+
- **CLI**: Click (for a robust command-line interface)

### 2.2 AI & Tooling
- **Vibe Tools**: Custom CLI tools (`vibe`) for PRD generation, test coverage improvement, and infrastructure management.
- **Prompts**: Version-controlled AI prompts in `prompts/`.

## 3. Project Structure
```text
/
├── vibe_tools/      # Core automation logic and CLI
├── specs/           # Markdown PRDs and specifications
├── prompts/         # AI prompt templates
├── project/         # Architecture and infrastructure definitions (YAML)
└── tests/           # Comprehensive test suite
```

## 4. Key Design Patterns
- **CLI-First Workflow**: All infrastructure and common tasks are driven by the `vibe` command.
- **PRD-Driven Development**: Changes start with a PRD in `specs/`, normalized into plans.
