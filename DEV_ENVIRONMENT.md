# Development Environment Setup Instructions

This document describes the development environment that is created when running `make setup` or `make install` (which calls `vibe-setup env` and `install.sh`).

## Overview

The setup process creates a managed Python environment using `pyenv` and `pyenv-virtualenv`, installs project dependencies, and initializes the project structure with configuration files and directories.

## Setup Process

### 1. Installation Methods

- **`make install`**: Runs `./install.sh` which can install globally via `pipx` or locally
- **`make setup`**: Runs `vibe-setup env` which sets up a managed Python environment
- **`vibe-setup env`**: Interactive setup that creates a pyenv-virtualenv environment

### 2. Python Environment Setup

The `vibe-setup env` command (default Python version: 3.11.10):

1. **Checks for prerequisites**:
   - Homebrew (required)
   - pyenv (installs if missing)
   - pyenv-virtualenv (installs if missing)

2. **Installs Python version**:
   - Installs the specified Python version via `pyenv install <version>`
   - Default: Python 3.11.10

3. **Creates virtualenv**:
   - Virtualenv name: `{project-name}-{python-version}` (e.g., `vibe-tools-3.11.10`)
   - Created via `pyenv virtualenv <python-version> <venv-name>`
   - Sets local Python version via `pyenv local <venv-name>`

4. **Records configuration**:
   - Saves environment details to `project/config.json`:
     ```json
     {
       "env": {
         "type": "pyenv-virtualenv",
         "python_version": "3.11.10",
         "venv_name": "vibe-tools-3.11.10",
         "path": "/path/to/project",
         "last_setup": "2026-01-06T..."
       }
     }
     ```

### 3. Dependency Installation

The `vibe-setup deps` command (called automatically by `vibe-setup env`):

1. **Installs essential tools**:
   - `ruff` (linter)
   - `pytest` (testing)
   - `pytest-cov` (coverage)
   - `mypy` (type checking)

2. **Installs project Python dependencies**:
   - If `pyproject.toml` exists: `pip install -e .` (editable install)
   - If `backend/requirements.txt` exists: `pip install -r backend/requirements.txt`
   - If `requirements.txt` exists: `pip install -r requirements.txt`

3. **Installs frontend dependencies**:
   - If `frontend/package.json` exists: `npm install --prefix frontend`

4. **Project dependencies** (from `pyproject.toml`):
   - click, gspread, google-auth, google-auth-oauthlib, python-dotenv
   - requests, rich, PyYAML, pytest, pytest-cov, pytest-asyncio
   - ruff, mypy, dspy-ai

### 4. Project Structure

The setup creates the following directory structure:

```
project/
├── config.json              # Main configuration file
├── state.json               # Project state tracking
├── legacy-state.json        # Legacy state file
├── architect-config.json    # Architect tool configuration
├── architect-session.json   # Architect session state
├── pm-config.json           # PM tool configuration
├── pm-session.json          # PM session state
├── prds/                    # PRD (Product Requirements Document) files
│   ├── architecture.yaml
│   ├── project_overview.yaml
│   ├── infrastructure.yaml
│   ├── cicd.yaml
│   └── prd_*.yaml           # Individual PRD files
├── logs/                    # Application logs
├── costs/                   # Cost tracking files
├── instructions/            # Global agent instructions
└── data/                    # Application data storage

specs/                       # Human-written specifications
├── architecture.md
├── infrastructure.md
└── *.md                     # Other spec files

prompts/                     # Override prompts (optional)
.env                        # Environment variables (API keys, etc.)
.python-version             # pyenv Python version file
```

### 5. Configuration Files

#### `.vibe_config.json` / `project/config.json`

Main configuration file containing:

- **`ralph`**: Ralph loop settings (review, tests, auto_merge)
- **`caffeinate`**: Prevent system sleep during long tasks
- **`use_google_sheets`**: Enable Google Sheets cost logging
- **`google_sheet_id`**: Google Sheet ID for cost logging
- **`verbose`**: Verbose logging mode
- **`default_budget`**: Max budget in USD for automated runs
- **`services`**: Connection details for supporting services:
  - `postgres`: PostgreSQL database
  - `redis`: Redis cache
  - `rabbitmq`: RabbitMQ message queue
  - `elasticsearch`: Elasticsearch search
  - `s3-linode`: MinIO/Linode S3-compatible storage
  - `s3-aws`: MinIO/AWS S3-compatible storage
  - `imgproxy`: Image proxy service
  - `mailhog`: Email testing service
- **`env`**: Python environment configuration (from `vibe-setup env`)

#### `.env` File

Environment variables (synced from config):
- `GOOGLE_API_KEY`: Google Gemini API key for DSPy/LLM access

### 6. Service Configuration

Services can be configured via `vibe-setup <service>` commands:

- `vibe-setup postgres`: Configure PostgreSQL connection
- `vibe-setup redis`: Configure Redis connection
- `vibe-setup rabbitmq`: Configure RabbitMQ connection
- `vibe-setup elasticsearch`: Configure Elasticsearch connection
- `vibe-setup s3-linode`: Configure Linode-compatible S3 storage
- `vibe-setup s3-aws`: Configure AWS-compatible S3 storage
- `vibe-setup imgproxy`: Configure imgproxy service
- `vibe-setup mailhog`: Configure MailHog email testing
- `vibe-setup api`: Configure API keys (Google Gemini)
- `vibe-setup google`: Configure Google Sheets integration
- `vibe-setup test`: Test connectivity for all configured services

Each service setup:
- Detects running Docker containers automatically
- Prompts for host, port, credentials
- Tests connectivity before saving
- Stores configuration in `project/config.json` under `services`

### 7. Available Commands

After setup, the following commands are available:

**CLI Commands**:
- `vibe`: Main CLI entry point
- `vibe-setup`: Setup and configuration commands
- `vibe-servers`: Manage Docker-based local services
- `vibe-staging`: Staging environment management

**Makefile Targets**:
- `make install`: Install dependencies
- `make setup`: Run environment setup
- `make test`: Run all tests
- `make test-backend`: Run backend tests
- `make test-frontend`: Run frontend tests
- `make coverage`: Run tests with coverage
- `make lint-backend`: Run backend linting (ruff, mypy)
- `make lint-frontend`: Run frontend linting (eslint)
- `make frontend-install`: Install frontend dependencies
- `make frontend-build`: Build frontend for production
- `make frontend-test`: Run frontend tests
- `make monitor`: Run progress monitor
- `make cleanup`: Clean up stale processes

### 8. Environment Verification

To verify the environment is correctly set up:

1. **Check Python environment**:
   ```bash
   python --version  # Should show 3.11.10
   which python      # Should point to pyenv virtualenv
   ```

2. **Check installed packages**:
   ```bash
   pip list          # Should show vibe-tools and dependencies
   ```

3. **Check configuration**:
   ```bash
   vibe-setup test   # Test all configured services
   vibe-setup dspy   # Test DSPy/LLM connectivity
   ```

4. **Check project structure**:
   ```bash
   ls -la project/   # Should show all directories
   ```

### 9. Shell Configuration

For pyenv to work correctly, add to `~/.zshrc` or `~/.bash_profile`:

```bash
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
```

### 10. Key Environment Variables

- `PYTHONPATH`: Set to `.` for running tests (via `PYTHONPATH=. pytest`)
- `GOOGLE_API_KEY`: Stored in `.env` file, loaded via `python-dotenv`
- Environment variables from `project/config.json` are synced to `.env`

### 11. Git Integration

- If not a git repository, setup prompts to initialize one
- `.gitignore` is automatically updated to exclude:
  - `project/` directory contents
  - `.env` file
  - `.vibe_config.json` (if exists in root)

### 12. Frontend Environment

If `frontend/package.json` exists:
- **Package manager**: npm
- **Test framework**: Vitest
- **Linter**: ESLint
- **TypeScript**: Enabled
- **Dependencies**: typescript, vitest, @types/node

## Development Workflow

1. **Initial Setup**:
   ```bash
   make install    # Or: ./install.sh
   make setup      # Or: vibe-setup env
   ```

2. **Configure Services** (optional):
   ```bash
   vibe-setup api      # Configure API keys
   vibe-setup postgres # Configure database
   vibe-setup test     # Verify all services
   ```

3. **Development**:
   ```bash
   make test           # Run tests
   make lint-backend   # Check code quality
   vibe status         # Check system status
   ```

4. **Frontend Development**:
   ```bash
   make frontend-install
   make frontend-test
   make frontend-run   # Development server
   ```

## Notes for AI Assistants

When working in this environment:

1. **Python Environment**: Always use the pyenv virtualenv. The `.python-version` file ensures the correct version is used.

2. **Configuration**: Check `project/config.json` for project settings and `project/config.json` under `services` for service connections.

3. **Dependencies**: Python dependencies are in `pyproject.toml`. Frontend dependencies are in `frontend/package.json`.

4. **Project Structure**: All runtime data (logs, costs, PRDs) is in `project/`. Specifications are in `specs/`.

5. **Testing**: Use `PYTHONPATH=. pytest` for backend tests. Frontend tests use `vitest`.

6. **Linting**: Backend uses `ruff` and `mypy`. Frontend uses `eslint`.

7. **Service Management**: Use `vibe-servers` commands to manage Docker-based local services.

8. **State Management**: Project state is tracked in `project/state.json`. Session state for interactive tools is in `project/*-session.json`.
