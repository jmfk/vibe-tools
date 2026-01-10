---
discussion_id: D_kwDOQzI0Lc4Ajlta
discussion_url: https://github.com/jmfk/vibe-tools/discussions/37
last_synced_at: '2026-01-10T15:24:35.391451'
sync_hash: b51d661d056e16fe57fa1d410358dc953d49b15585b3ae44c68fba0ec321e3a7
---

# Configuration System

## Overview
- **Problem statement**: Projects need centralized configuration for services (databases, queues, caches), AI agent settings, cost tracking, and workflow preferences. Configuration must be easy to edit, support multiple environments, and provide sensible defaults.
- **User benefits**: Single source of truth for all project settings, easy service connection management, reusable configuration across commands, environment-specific overrides, and automatic Docker container detection.
- **Success criteria**: Configuration system supports all service types, validates settings, provides helpful defaults, detects running Docker containers, and persists user preferences.

## Feature Inspiration
The configuration system manages `.vibe_config.json` in the project root, storing service connection details, AI agent preferences, cost tracking settings, and workflow flags. It supports interactive setup via `vibe-setup` commands, automatically detects running Docker containers for local services, and provides validation and error handling.

**Key capabilities**:
- Service configuration (Postgres, Redis, RabbitMQ, Elasticsearch, S3, imgproxy, etc.)
- AI agent configuration (model selection, API keys)
- Cost tracking settings (Google Sheets integration, budget limits)
- Workflow preferences (caffeinate, verbose mode, auto-merge)
- Docker container auto-detection
- Environment variable integration

## Frontend
N/A - Configuration files and CLI commands.

## Backend
- **Configuration File Format**: JSON file (`.vibe_config.json`) with nested structure:
  - `services`: Map of service names to connection details
  - `ralph`: Ralph loop settings (review, tests, auto_merge)
  - `caffeinate`: Boolean flag for system sleep prevention
  - `use_google_sheets`: Boolean for cost logging
  - `google_sheet_id`: Google Sheet ID for cost tracking
  - `verbose`: Boolean for verbose output
  - `default_budget`: Max budget in USD for automated runs
- **Service Configuration Schema**: Each service includes:
  - `host`: Service hostname/IP
  - `port`: Service port
  - `user`: Username (if applicable)
  - `password`: Password (if applicable)
  - `database`: Database name (if applicable)
  - `docker_container_name`: Detected Docker container name
  - Service-specific fields (virtual_host, region, addressing_style, etc.)
- **Configuration Loading**: `load_config()` function reads and validates config, merges with defaults, handles missing files gracefully.
- **Configuration Saving**: `save_config()` function writes config with proper formatting, preserves user comments if possible.
- **Docker Detection**: `vibe-setup` commands use `docker ps` and `docker inspect` to detect running containers and pre-fill host/port.
- **Environment Variables**: Supports `.env` file via python-dotenv, allows overriding config values via environment variables.

## Infrastructure
- **Storage**: `.vibe_config.json` in project root (user-editable, typically git-ignored).
- **Validation**: Schema validation for required fields, type checking, connection testing via `vibe-setup test`.
- **Backup**: Users can manually backup config file, no automatic versioning (git handles this).
- **Secrets Management**: Passwords stored in plain text (user responsibility), can be moved to environment variables.

## Architecture and Constraints
- **Default Values**: System provides sensible defaults for all settings, allowing minimal config files.
- **Service Discovery**: Docker container detection reduces manual configuration for local development.
- **Validation**: Connection testing available but not enforced (allows offline configuration).
- **Security**: Passwords in plain text (acceptable for local dev, users should use env vars for production).
- **Extensibility**: New services can be added by extending `SERVICE_DEFINITIONS` in `setup.py`.

## Success Criteria
- All supported services configurable via `vibe-setup`
- Docker containers automatically detected and pre-filled
- Configuration validated on load
- Missing config handled gracefully with defaults
- Service connections testable via `vibe-setup test`
- Config persists across command invocations

## Acceptance Tests
1. **Initial Setup**: Run `vibe-setup postgres`, verify interactive prompts, Docker detection works, config saved
2. **Config Loading**: Create minimal config, run any command, verify config loaded correctly
3. **Missing Config**: Delete config file, run command, verify defaults used
4. **Service Testing**: Configure service, run `vibe-setup test`, verify connection tested
5. **Docker Detection**: Start Postgres container, run `vibe-setup postgres`, verify host/port pre-filled
6. **Multiple Services**: Configure 5+ services, verify all saved correctly
7. **Config Validation**: Create invalid config (wrong types), verify graceful error handling
8. **Environment Override**: Set env var, verify overrides config file value