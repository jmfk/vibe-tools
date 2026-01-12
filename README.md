# vibe-tools

Global commands for Cursor Ralph loop and coverage improvement.

## Configuration

The tools use a `.vibe_config.json` file in the project root for configuration. This file is automatically created and updated when running `vibe-setup google`.

### Example `.vibe_config.json`

```json
{
  "ralph": {
    "review": true,
    "tests": true,
    "auto_merge": false
  },
  "caffeinate": true,
  "use_google_sheets": true,
  "google_sheet_id": "YOUR_SHEET_ID_HERE",
  "verbose": false,
  "default_budget": 5.0,
  "services": {
    "postgres": {
      "host": "localhost",
      "port": 5432,
      "user": "postgres",
      "password": "",
      "database": "app_db",
      "docker_container_name": "postgres-local"
    },
    "redis": {
      "host": "localhost",
      "port": 6379,
      "password": "",
      "database": 0,
      "docker_container_name": "redis-local"
    },
    "rabbitmq": {
      "host": "localhost",
      "port": 5672,
      "user": "guest",
      "password": "guest",
      "virtual_host": "/",
      "docker_container_name": "rabbitmq-local"
    },
    "elasticsearch": {
      "host": "localhost",
      "port": 9200,
      "scheme": "http",
      "username": "",
      "password": "",
      "docker_container_name": "es-local"
    },
    "s3-linode": {
      "host": "localhost",
      "port": 9000,
      "access_key": "minioadmin",
      "secret_key": "minioadmin",
      "region": "us-east-1",
      "addressing_style": "path",
      "signature_version": "s3v4"
    },
    "s3-aws": {
      "host": "localhost",
      "port": 9010,
      "access_key": "minioadmin",
      "secret_key": "minioadmin",
      "region": "us-east-1",
      "addressing_style": "virtual",
      "signature_version": "s3v4"
    }
  }
}
```

- `caffeinate`: Prevent system sleep during long-running tasks.
- `use_google_sheets`: Whether to log LLM costs to Google Sheets.
- `google_sheet_id`: The ID of the Google Sheet to log to.
- `verbose`: Whether to output detailed logs (like prompts) to the terminal.
- `default_budget`: Max budget in USD for automated runs (can be overridden per run).
- `services`: Connection details for supporting servers (Postgres, Redis, RabbitMQ, Elasticsearch, etc.). Entries under this map store host, port, credentials, and any detected Docker container so every project command can reuse a shared backend.

### Service Configuration

Use the `vibe-setup` command to record connection details for the supporting services your projects rely on:

- `vibe-setup postgres`
- `vibe-setup redis`
- `vibe-setup rabbitmq`
- `vibe-setup elasticsearch`
- `vibe-setup s3-linode`
- `vibe-setup s3-aws`
- `vibe-setup imgproxy`
- `vibe-setup api`
- `vibe-setup google`
- `vibe-setup test`: Verify connectivity for all configured services.

Each command walks you through host, port, and credential prompts and attempts to detect a running Docker container for that service (`docker ps`/`docker inspect`) so the host and port default to what is already running locally. The answers are stored under the `services` map in `.vibe_config.json` and can be reused by every tool that needs a database, queue, cache, or search backend.

## Installation

```bash
pip install -e .
```

## Usage

### CLI

The `vibe` command is the main entry point:

```bash
vibe --help
```

### Key Commands

- `vibe init`: Initialize templates and prompt directories.
- `vibe status`: Display a comprehensive system status report (costs, PRDs, servers, logs).
- `vibe docs`: Display the project documentation (README.md).
- `vibe architect`: Interactive Architecture & Infrastructure manager (preferred for system design).
- `vibe pm`: Interactive PRD & Specification manager (preferred for requirement gathering).
- `vibe prd`: Interactive PRD writer with slash commands.
- `vibe rerun <prd_id>`: Reset a PRD's state and branch to allow rerunning from scratch.
- `vibe cleanup`: Clean up stale pytest, agent, and caffeinate processes.
- `vibe memory`: Save a global instruction ("memory") always sent to the agent.
- `vibe memory`: Save a global instruction.
- `vibe history`: Check the status of all PRDs.
- `vibe cost`: View total estimated cost of LLM usage.
- `vibe-setup api`: Configure API keys for Google Gemini/DSPy.
- `vibe-setup google`: Configure Google Sheets for cost logging.

## Vibe Architect

`vibe architect` is an interactive shell for managing and refining your project's **Architecture** and **Infrastructure** specifications. It uses an AI agent to help you reason about your system and automatically update your `.md` files in `product/`.

### Key Features

- **Interactive Shell**: Persistent history, tab completion for slash commands, and multi-line prompt support.
- **Two Modes**:
  - **ASK** (Default): The agent provides analysis and guidance without modifying files.
  - **AGENT**: The agent is authorized to propose machine-readable updates to `architecture.md` and `infrastructure.md`.
- **Session Persistence**: Your history, pending prompts, and attached context files are saved between sessions in `implementation/architect-session.json`.
- **Editor Integration**: Configure your favorite Markdown or Code editor (e.g., Typora, VS Code) to open response files or specifications.
- **Context Management**: Attach additional files to the agent's context using `/f add`.
- **Session Memory**: Add persistent instructions that are sent with every prompt using `/a` or `/add`.

### Slash Commands

- `/send`, `/s`: Dispatch the current pending prompt to the Architect.
- `/reset`, `/r`: Clear the current session memory and pending prompt.
- `/add`, `/a <text>`: Add persistent instructions to the session memory.
- `/mode`, `/m [ASK|AGENT]`: Switch between interaction modes.
- `/files`, `/f [list|add <path>|remove <path>]`: Manage additional files included in the prompt context.
- `/list memory`, `/l`: View your pending prompt, session memory, and history summary.
- `/conf [md|code] <cmd>`: Configure external editors (e.g., `/conf md typora`).
- `/help`, `/h`: Show available commands.
- `/c`: Clear the terminal prompt history.
- `/exit`, `/q`: Exit the session.

### Local Infrastructure

Manage local development servers via Docker using `vibe-servers`:

- `vibe-servers list`: List supported servers (Postgres, Redis, RabbitMQ, Elasticsearch, MailHog, MinIO-Linode, MinIO-AWS, imgproxy) and their status.
- `vibe-servers install <service>`: Pull and run the Docker container for a service. Use `minio` as a shorthand to choose between Linode and AWS styles.
- `vibe-servers start/stop <service>`: Start or stop one or all servers.
- `vibe-servers logs <service>`: View logs for one or all servers.
- `vibe-servers status`: Show detailed status and port mappings.
- `vibe-servers remove <service>`: Remove a service container.

### Linode Object Storage Compatibility

The local MinIO setup is configured to be "Linode-first," ensuring that development on MinIO seamlessly transitions to Linode Object Storage:

- **Path-Style Addressing**: Uses `endpoint/bucket/file` format (standard for Linode).
- **Signature Version**: Enforces `s3v4` authentication.
- **Protocol Detection**: Supports both `http` (local) and `https` (production) via endpoint URL configuration.
- **S3 Protocol URLs**: Overrides default behavior to support `s3://` protocol for internal services like `imgproxy`.

### Loop Scripts

- `vibe coverage`: Run the loop to improve test coverage.
- `vibe test-fix`: Run the loop to fix failing tests.
- `vibe normalize`: Normalize human-written specs into PRDs.

## Specs & PRDs

1. **Start with a human spec.** Write a normative spec in `product/` (for example `product/01_platform_vision.md`). That markdown is the source of truth for requirements.
2. **Global Truths.** Certain files in `product/` represent the persistent state of the system and are injected into every Ralph prompt as context:
   - `architecture.md` -> `prds/architecture.yaml`
   - `project_overview.md` -> `prds/project_overview.yaml`
   - `infrastructure.md` -> `prds/infrastructure.yaml`
   - `cicd.md` -> `prds/cicd.yaml`
3. **Convert specs into Ralph-ready PRDs.** Ralph only reads `prds/prd_*.yaml` for implement tasks. Transform each spec into a YAML file using `vibe normalize`. Global truths are converted without the `prd_` prefix and are used purely for context.
4. **Global Agent Instructions.** Use `vibe memory` to save global guidelines into `instructions/`. Ralph reads all files in this directory and injects them into every agent prompt.

## Development


