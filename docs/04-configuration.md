# Configuration

## Configuration Files

vibe-tools uses multiple configuration files for different purposes:

- **`project/config.json`**: Project-specific configuration (formerly `.vibe_config.json`)
- **`~/.vibe/config.json`**: Global user configuration
- **`.env`**: Environment variables (API keys, secrets)
- **`project/state.json`**: Project state and phase tracking
- **`~/.vibe/servers.json`**: Global server configurations

## Project Configuration (`project/config.json`)

The main configuration file is automatically created and updated when running setup commands.

### Structure

```json
{
  "ralph": {
    "review": true,
    "tests": true,
    "auto_merge": false
  },
  "caffeinate": true,
  "use_google_sheets": false,
  "google_sheet_id": "",
  "verbose": false,
  "default_budget": 5.0,
  "iterations": {
    "coverage": 5,
    "implementation": 10,
    "debug": 5
  },
  "coverage_targets": {
    "backend": 85,
    "frontend": 85,
    "infra": 85
  },
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
    }
  }
}
```

### Configuration Options

#### Ralph Agent Settings

**`ralph.review`** (boolean, default: `true`)
- Enable code review during implementation

**`ralph.tests`** (boolean, default: `true`)
- Run tests during implementation

**`ralph.auto_merge`** (boolean, default: `false`)
- Automatically merge branches after successful implementation
- When enabled, uses the automerge branch name from configuration

#### System Settings

**`caffeinate`** (boolean, default: `false`)
- Prevent system sleep during long-running tasks
- Can be overridden with `--caffeinate` flag

**`verbose`** (boolean, default: `false`)
- Output detailed logs (like prompts) to the terminal
- Can be overridden with `--verbose` flag

**`default_budget`** (float, default: `5.0`)
- Maximum budget in USD for automated runs
- Can be overridden per run

#### Google Sheets Integration

**`use_google_sheets`** (boolean, default: `false`)
- Enable cost logging to Google Sheets

**`google_sheet_id`** (string, default: `""`)
- The ID of the Google Sheet to log costs to
- Set via `vibe-setup google`

#### Iteration Limits

**`iterations.coverage`** (integer, default: `5`)
- Maximum iterations for coverage improvement loop

**`iterations.implementation`** (integer, default: `10`)
- Maximum iterations for implementation loop

**`iterations.debug`** (integer, default: `5`)
- Maximum iterations for debug phase

#### Coverage Targets

**`coverage_targets.backend`** (integer, default: `85`)
- Target test coverage percentage for backend code

**`coverage_targets.frontend`** (integer, default: `85`)
- Target test coverage percentage for frontend code

**`coverage_targets.infra`** (integer, default: `85`)
- Target test coverage percentage for infrastructure code

#### Service Configuration

**`services.<service_name>`** (object)
- Connection details for supporting services
- Each service can have:
  - `host`: Service hostname
  - `port`: Service port
  - Service-specific fields (user, password, database, etc.)
  - `docker_container_name`: Detected Docker container name

See [Service Configuration](#service-configuration) for details.

## Environment Variables (`.env`)

Environment variables are loaded from `.env` file in the project root. These typically contain sensitive information like API keys.

### Required Variables

**`GOOGLE_API_KEY`**
- Google API key for Gemini/DSPy integration
- Set via `vibe-setup api`

### Optional Variables

**`DSPY_API_KEY`**
- Alternative API key for DSPy if different from Google API key

**`CURSOR_API_KEY`**
- Cursor API key for Cursor agent integration

## Service Configuration

Services are configured using `vibe-setup <service>` commands. Each service has its own configuration structure.

### Available Services

#### PostgreSQL (`vibe-setup postgres`)
```json
{
  "host": "localhost",
  "port": 5432,
  "user": "postgres",
  "password": "postgres",
  "database": "app_db",
  "docker_container_name": "postgres-local"
}
```

#### Redis (`vibe-setup redis`)
```json
{
  "host": "localhost",
  "port": 6379,
  "password": "",
  "database": 0,
  "docker_container_name": "redis-local"
}
```

#### RabbitMQ (`vibe-setup rabbitmq`)
```json
{
  "host": "localhost",
  "port": 5672,
  "user": "guest",
  "password": "guest",
  "virtual_host": "/",
  "docker_container_name": "rabbitmq-local"
}
```

#### Elasticsearch (`vibe-setup elasticsearch`)
```json
{
  "host": "localhost",
  "port": 9200,
  "scheme": "http",
  "username": "",
  "password": "",
  "docker_container_name": "es-local"
}
```

#### S3 Object Storage

**Linode-style (`vibe-setup s3-linode`)**
```json
{
  "host": "localhost",
  "port": 9000,
  "access_key": "minioadmin",
  "secret_key": "minioadmin",
  "region": "us-east-1",
  "addressing_style": "path",
  "signature_version": "s3v4",
  "console_port": 9001
}
```

**AWS-style (`vibe-setup s3-aws`)**
```json
{
  "host": "localhost",
  "port": 9010,
  "access_key": "minioadmin",
  "secret_key": "minioadmin",
  "region": "us-east-1",
  "addressing_style": "virtual",
  "signature_version": "s3v4",
  "console_port": 9011
}
```

#### MailHog (`vibe-setup mailhog`)
```json
{
  "host": "localhost",
  "port": 1025,
  "web_port": 8025,
  "docker_container_name": "mailhog-local"
}
```

#### imgproxy (`vibe-setup imgproxy`)
```json
{
  "host": "localhost",
  "port": 8080,
  "docker_container_name": "imgproxy-local"
}
```

### Docker Container Detection

When configuring services, `vibe-setup` automatically detects running Docker containers:
- Scans `docker ps` output
- Matches containers by keywords (e.g., "postgres", "redis")
- Pre-fills host and port from container configuration
- Stores container name in `docker_container_name` field

## Global Configuration (`~/.vibe/config.json`)

Global configuration stored in user home directory. Currently used for:
- Global server configurations
- User preferences (future)

## Project State (`project/state.json`)

Tracks project implementation state:

```json
{
  "phases": {
    "architect": {"status": "completed"},
    "pm": {"status": "completed"},
    "normalize": {"status": "completed"},
    "setup": {"status": "completed"},
    "deps": {"status": "completed"},
    "implement": {"status": "in_progress"},
    "testing": {"status": "pending"},
    "infra": {"status": "pending"},
    "deploy": {"status": "pending"}
  },
  "plans": {
    "plan_1": {
      "prd_id": "prd_01_feature",
      "branch": "vibe/plan_1",
      "status": "in_progress"
    }
  },
  "main_branch": "main",
  "automerge_branch": "automerge"
}
```

## Configuration Management

### Viewing Configuration

**Check current configuration:**
```bash
vibe status
```

**View specific config file:**
```bash
cat project/config.json
```

### Updating Configuration

**Interactive setup:**
```bash
vibe-setup <service>    # Update service configuration
vibe-setup api          # Update API keys
vibe-setup google       # Update Google Sheets config
```

**Manual editing:**
- Edit `project/config.json` directly
- Configuration is validated on next command execution

### Configuration Migration

The system automatically migrates configuration from old locations:
- `.vibe_config.json` → `project/config.json`
- `prds/` → `project/prds/`
- `logs/` → `project/logs/`
- Other legacy paths → `project/` directory

Migration happens automatically on first command execution.

## Best Practices

1. **Use `vibe-setup` for service configuration**: Interactive prompts ensure correct format
2. **Store secrets in `.env`**: Never commit API keys or passwords
3. **Version control `config.json`**: Non-sensitive configuration can be committed
4. **Use global config for defaults**: Set user preferences in `~/.vibe/config.json`
5. **Check `vibe status` regularly**: Verify configuration is correct

## Troubleshooting

**Configuration not loading:**
- Check file exists: `ls project/config.json`
- Verify JSON syntax: `python -m json.tool project/config.json`
- Check file permissions

**Service connection issues:**
- Verify service is running: `vibe-servers status`
- Test connectivity: `vibe-setup test`
- Check configuration: `vibe status`

**Migration issues:**
- Old files may still exist in root directory
- Run `vibe init` to ensure proper structure
- Check `project/` directory for migrated files

See [Troubleshooting](12-troubleshooting.md) for more help.
