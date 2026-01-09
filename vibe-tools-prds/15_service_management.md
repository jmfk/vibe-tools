# Service Management

## Overview
- **Problem statement**: Developers need easy management of local development services (Postgres, Redis, RabbitMQ, etc.) via Docker. The system should provide simple commands to install, start, stop, and monitor services.
- **User benefits**: One-command service management, consistent local development environment, Docker-based isolation, and easy service discovery.
- **Success criteria**: `vibe-servers` successfully manages all supported services, provides clear status, handles Docker operations correctly, and supports all common operations.

## Feature Inspiration
The `vibe-servers` command provides Docker-based management of local development services. It supports multiple services (Postgres, Redis, RabbitMQ, Elasticsearch, MailHog, MinIO variants, imgproxy), provides install/start/stop/status/logs operations, and automatically detects running containers.

**Key capabilities**:
- Service installation (Docker pull and run)
- Service lifecycle (start, stop, restart)
- Status reporting (running, ports, containers)
- Log viewing (service logs)
- Service removal (container cleanup)
- Docker container detection

## Frontend
N/A - CLI commands.

## Backend
- **Supported Services**: 
  - Postgres (with pgvector)
  - Redis
  - RabbitMQ (with management UI)
  - Elasticsearch
  - MailHog
  - MinIO (Linode and AWS styles)
  - imgproxy
- **Service Operations**:
  - `list`: List all supported services and their status
  - `install <service>`: Pull Docker image and start container
  - `start <service>`: Start service container
  - `stop <service>`: Stop service container
  - `status`: Show detailed status (ports, containers, running state)
  - `logs <service>`: View service logs
  - `remove <service>`: Remove service container
- **Docker Integration**:
  - Uses `docker ps` to detect running containers
  - Uses `docker inspect` to get container details
  - Manages container lifecycle
  - Handles port mappings
- **Service Configuration**: 
  - Default configurations in `DEFAULT_SERVER_CONFIGS`
  - User configurations in global servers file
  - Merges defaults with user configs
- **Status Detection**: 
  - Checks if containers are running
  - Reports port mappings
  - Shows container names

## Infrastructure
- **Docker**: Requires Docker installed and running.
- **Container Management**: Creates, starts, stops, removes containers.
- **Port Management**: Maps service ports to host ports.
- **Configuration Storage**: Global server configs stored in project config.

## Architecture and Constraints
- **Docker Dependency**: Requires Docker, fails gracefully if not available.
- **Port Conflicts**: Must handle port conflicts gracefully.
- **Container Naming**: Uses consistent naming (`vibe-{service}`).
- **Platform Support**: Works on Unix, macOS, Windows (with Docker).

## Success Criteria
- All services installable and manageable
- Status reporting accurate
- Docker operations work correctly
- Port mappings correct
- Log viewing works
- Error handling robust

## Acceptance Tests
1. **Service List**: Run `vibe-servers list`, verify all services shown
2. **Install**: Install service, verify container created and running
3. **Start/Stop**: Start and stop service, verify state changes
4. **Status**: Check status, verify accurate information
5. **Logs**: View logs, verify logs displayed
6. **Remove**: Remove service, verify container deleted
7. **Port Mapping**: Verify ports mapped correctly
8. **Docker Detection**: Verify running containers detected
9. **Error Handling**: Test with Docker not running, verify graceful error
