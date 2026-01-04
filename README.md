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
- `vibe ralph`: Run the main PRD processing loop.
- `vibe setup-google`: Configure Google Sheets for cost logging.
- `vibe cost`: View total estimated cost of LLM usage.
- `vibe history`: Check the status of all PRDs.

### Loop Scripts

- `vibe ralph`: Run the Ralph loop for automated coding.
- `vibe coverage`: Run the loop to improve test coverage.
- `vibe test-fix`: Run the loop to fix failing tests.
- `vibe normalize`: Normalize human-written specs into PRDs.

## Development

Monitor the status of loops using `vibe monitor`:

```bash
vibe monitor
```

