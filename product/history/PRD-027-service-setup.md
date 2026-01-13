# Service Setup

## Overview
- **Problem statement**: Projects need to configure connection details for various services (databases, queues, caches, APIs). The setup process should be interactive, detect running Docker containers, and validate connections.
- **User benefits**: Interactive service configuration, automatic Docker detection, connection validation, and persistent configuration storage.
- **Success criteria**: `vibe-setup` successfully configures all service types, detects Docker containers, validates connections, and saves configuration correctly.

## Feature Inspiration
The `vibe-setup` command provides interactive configuration for services. It prompts for connection details (host, port, credentials), automatically detects running Docker containers to pre-fill values, tests connections, and saves configuration to `.vibe_config.json`.

**Key capabilities**:
- Interactive service configuration
- Docker container auto-detection
- Connection testing
- Configuration persistence
- Multiple service types supported

## Frontend
N/A - CLI interactive prompts.

## Backend
- **Supported Services**:
  - `postgres`: PostgreSQL database
  - `redis`: Redis cache
  - `rabbitmq`: RabbitMQ message broker
  - `elasticsearch`: Elasticsearch search engine
  - `s3-linode`: S3-compatible storage (Linode style)
  - `s3-aws`: S3-compatible storage (AWS style)
  - `imgproxy`: Image proxy service
  - `api`: API keys (Google Gemini, DSPy)
  - `google`: Google Sheets integration
  - `test`: Test all configured services
- **Setup Process**:
  1. Detect running Docker container for service
  2. Pre-fill host/port from container if found
  3. Prompt for connection details
  4. Validate inputs
  5. Test connection (if applicable)
  6. Save to `.vibe_config.json`
- **Docker Detection**: 
  - Uses `docker ps` to find running containers
  - Uses `docker inspect` to get container details
  - Matches container names (e.g., `vibe-postgres`)
  - Extracts host and port from container
- **Connection Testing**: 
  - Attempts connection to service
  - Validates credentials
  - Reports success/failure
- **Configuration Schema**: Each service stores:
  - `host`: Service hostname
  - `port`: Service port
  - `user`: Username (if applicable)
  - `password`: Password (if applicable)
  - `database`: Database name (if applicable)
  - `docker_container_name`: Detected container name
  - Service-specific fields

## Infrastructure
- **Docker Integration**: Detects running containers.
- **Configuration Storage**: Saves to `.vibe_config.json`.
- **Connection Libraries**: Uses service-specific libraries for testing (psycopg2, redis, etc.).

## Architecture and Constraints
- **Interactive Prompts**: Must be user-friendly, provide defaults.
- **Docker Detection**: Optional, graceful fallback if Docker not available.
- **Connection Testing**: May require service-specific libraries.
- **Security**: Passwords stored in plain text (acceptable for local dev).

## Success Criteria
- All service types configurable
- Docker detection works correctly
- Connection testing accurate
- Configuration saved correctly
- Interactive prompts clear and helpful

## Acceptance Tests
1. **Service Setup**: Configure each service type, verify saved correctly
2. **Docker Detection**: Start container, run setup, verify pre-filled values
3. **Connection Testing**: Configure service, verify connection tested
4. **Configuration Persistence**: Configure service, restart, verify config loaded
5. **Interactive Prompts**: Verify prompts clear, defaults helpful
6. **Test Command**: Run `vibe-setup test`, verify all services tested
7. **Error Handling**: Test with invalid inputs, verify error handling
8. **Multiple Services**: Configure multiple services, verify all saved

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-027
title: Service Setup
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.014622'
updated_at: '2026-01-13T20:07:27.807507'
discussion_id: null
discussion_url: https://github.com/jmfk/vibe-tools/discussions/41
last_synced_at: null
sync_hash: null
issue_number: null
```
</details>

<!-- vibe-id: PRD-027 -->
