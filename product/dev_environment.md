# Development Environment Specification

## 1. Overview
The vibe-tools development environment is designed for a CLI-first and Desktop-integrated workflow. It consists of a Python-based CLI (`vibe`) and a Tauri-based Desktop application. The environment is local-only, requiring no backend servers, databases, or Docker instances.

## 2. Build Components

### 2.1 Backend CLI (Python)
- **Language**: Python 3.11
- **Build commands**: `pip install -e .` or global installation via `pipx install -e .`
- **Dependencies**: `click`, `google-genai`, `rich`, `PyYAML`, `pydantic`.
- **Build outputs**: The `vibe` CLI tool.
- **Verification**: Run `vibe --help` to verify the installation.

### 2.2 Desktop App (Tauri)
- **Framework**: Tauri (Rust + Frontend)
- **Frontend**: React/TypeScript
- **Build commands**: 
  - Frontend: `npm install` (in `src-tauri` or root depending on structure)
  - Tauri: `cargo tauri build` or `cargo tauri dev`
- **Dependencies**: 
  - Rust (latest stable)
  - Node.js 20+
  - Tauri CLI
- **Build outputs**: Native desktop application.
- **Verification**: Run `cargo tauri dev` to launch the development version.

## 3. Development Environment Setup

### 3.1 Prerequisites
- **Python 3.11+**: Managed via `pyenv` recommended.
- **Rust**: Installed via `rustup`.
- **Node.js**: Version 20+ recommended.
- **pipx**: For global CLI tool management.

### 3.2 Environment Variables
The environment relies on a `.env` file in the project root:
- `GOOGLE_API_KEY`: Required for AI orchestration via `google-genai`.

### 3.3 Installation
Installation is handled via the `install.sh` script, which:
1. Installs the Python CLI globally via `pipx`.
2. Sets up the local development environment for the Python core.
3. (Planned) Handles Tauri/Rust environment verification.

## 4. Build System & Commands

### 4.1 CLI Development
- `make install-backend`: Install Python dependencies.
- `make test-backend`: Run pytest for the CLI.
- `make lint-backend`: Run `ruff` and `mypy`.

### 4.2 Desktop App Development
- `make install-frontend`: Install npm dependencies.
- `make dev-desktop`: Start the Tauri development environment (`cargo tauri dev`).
- `make build-desktop`: Build the production desktop application.

### 4.3 General
- `make test`: Run all tests (CLI & Desktop).
- `make lint`: Run all linters.
- `make clean`: Remove build artifacts and temporary files.

## 5. Logging & Debugging
- **CLI Logs**: Stored in `implementation/logs/`.
- **Desktop Logs**: Available via the Tauri console during development.
- **Log Levels**: Support for `DEBUG`, `INFO`, `WARNING`, `ERROR`.