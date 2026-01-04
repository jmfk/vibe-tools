# vibe-tools

Global commands for Cursor Ralph loop and coverage improvement.

## Configuration

The tools use a `.vibe_config.json` file in the project root for configuration. This file is automatically created and updated when running `vibe setup-google` or on the first run of `vibe ralph`.

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
    }
  }
}
```

- `ralph`: Default quality gates for the `vibe ralph` loop.
- `caffeinate`: Prevent system sleep during long-running tasks.
- `use_google_sheets`: Whether to log LLM costs to Google Sheets.
- `google_sheet_id`: The ID of the Google Sheet to log to.
- `verbose`: Whether to output detailed logs (like prompts) to the terminal.
- `default_budget`: Max budget in USD for automated runs (can be overridden per run).
- `services`: Connection details for supporting servers (Postgres, Redis, RabbitMQ, Elasticsearch, etc.). Entries under this map store host, port, credentials, and any detected Docker container so every project command can reuse a shared backend.

### Service Configuration

Use the new setup commands to record connection details for the supporting services your projects rely on:

- `vibe setup-postgres`
- `vibe setup-redis`
- `vibe setup-rabbitmq`
- `vibe setup-elasticsearch`

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
- `vibe write-prd`: Start an interactive interview to generate a new PRD spec.
- `vibe review-prd`: List and view markdown specs with optional agentic review.
- `vibe remember`: Save a global instruction ("memory") always sent to the agent.
- `vibe ralph`: Run the main PRD processing loop.
- `vibe history`: Check the status of all PRDs.
- `vibe setup-google`: Configure Google Sheets for cost logging.
- `vibe cost`: View total estimated cost of LLM usage.

### Loop Scripts

- `vibe ralph`: Run the Ralph loop for automated coding.
- `vibe coverage`: Run the loop to improve test coverage.
- `vibe test-fix`: Run the loop to fix failing tests.
- `vibe normalize`: Normalize human-written specs into PRDs.

## Specs & PRDs

1. **Start with a human spec.** Write a normative spec in `specs/` (for example `specs/prd_00_platform_vision_system_boundaries.md`). That markdown is the source of truth for requirements, success criteria, failure modes, etc.
2. **Infrastructure and CI/CD Upgrades.** You can place infrastructure and CI/CD specs in `specs/infra/` and `specs/cicd/`. When normalized, these will be prefixed with `infra_` or `cicd_`. Ralph automatically finds the highest-numbered file for each and includes it as shared context in every prompt.
3. **Convert the spec into a Ralph-ready PRD.** Ralph only reads `prds/prd_*.yaml`, `prds/infra_*.yaml`, and `prds/cicd_*.yaml`. Transform each spec into a YAML file using `vibe normalize`. Keep the numbered prefix so Ralph can process them in order or identify the latest version for context.
4. **Provide shared context documents.** Ralph injects `prds/architecture.yaml` and `prds/project_overview.yaml` into every prompt. It also includes the latest `infra_*.yaml` and `cicd_*.yaml`.
5. **Global Agent Instructions.** Use `vibe remember` to save global guidelines (like syntax style or coding standards) into `instructions/`. Ralph reads all files in this directory and injects them into every agent prompt.
6. **Understand the Ralph loop.** `vibe_tools/ralph.py` reads the PRD directory, includes the context files, and prompts the agent until it emits `<promise>DONE</promise>` before moving on to quality gates.

## Development

Monitor the status of loops using `vibe monitor`:

```bash
vibe monitor
```

