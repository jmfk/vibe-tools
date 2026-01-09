# Infrastructure Management

## Overview

vibe-tools provides comprehensive infrastructure management through the `vibe-servers` command and service configuration system. This enables consistent local development environments using Docker containers.

## Local Development Servers

### Supported Services

- **PostgreSQL**: Database with pgvector extension
- **Redis**: In-memory data store
- **RabbitMQ**: Message broker with management UI
- **Elasticsearch**: Search engine
- **MailHog**: Email testing tool
- **MinIO (Linode-style)**: S3-compatible object storage (path addressing)
- **MinIO (AWS-style)**: S3-compatible object storage (virtual addressing)
- **imgproxy**: On-the-fly image resizing and conversion

### Service Management

**List all services:**
```bash
vibe-servers list
```

**Install a service:**
```bash
vibe-servers install postgres
vibe-servers install redis
vibe-servers install minio  # Prompts for Linode or AWS style
```

**Start/Stop services:**
```bash
vibe-servers start postgres
vibe-servers stop postgres
vibe-servers start all      # Start all installed services
vibe-servers stop all      # Stop all installed services
```

**View logs:**
```bash
vibe-servers logs postgres
vibe-servers logs          # All services
```

**Check status:**
```bash
vibe-servers status
```

**Remove a service:**
```bash
vibe-servers remove postgres
```

## Service Configuration

### Configuration via vibe-setup

Configure service connections interactively:

```bash
vibe-setup postgres
vibe-setup redis
vibe-setup rabbitmq
vibe-setup elasticsearch
vibe-setup s3-linode
vibe-setup s3-aws
vibe-setup imgproxy
```

### Docker Container Detection

When configuring services, `vibe-setup` automatically:
1. Scans running Docker containers
2. Matches containers by keywords
3. Pre-fills host and port from container
4. Stores container name in configuration

### Configuration Storage

Service configurations are stored in:
- **Project config**: `project/config.json` (project-specific)
- **Global config**: `~/.vibe/config.json` (user defaults)

## Service Details

### PostgreSQL

**Default Configuration:**
- Image: `pgvector/pgvector:pg16`
- Port: 5432
- User: `postgres`
- Password: `postgres` (configurable)

**Installation:**
```bash
vibe-servers install postgres
```

**Configuration:**
```bash
vibe-setup postgres
```

**Connection Details:**
- Host: `localhost`
- Port: `5432`
- Database: Project name (default)

### Redis

**Default Configuration:**
- Image: `redis:alpine`
- Port: 6379
- No password (default)

**Installation:**
```bash
vibe-servers install redis
```

**Configuration:**
```bash
vibe-setup redis
```

### RabbitMQ

**Default Configuration:**
- Image: `rabbitmq:3-management`
- Ports: 5672 (AMQP), 15672 (Management UI)
- User: `guest`
- Password: `guest`

**Management UI:**
- URL: `http://localhost:15672`
- Login: `guest` / `guest`

### Elasticsearch

**Default Configuration:**
- Image: `elasticsearch:8.11.1`
- Port: 9200
- Security: Disabled for local dev

**Installation:**
```bash
vibe-servers install elasticsearch
```

### MailHog

**Default Configuration:**
- Image: `mailhog/mailhog`
- Ports: 1025 (SMTP), 8025 (Web UI)

**Web UI:**
- URL: `http://localhost:8025`

### MinIO (S3 Object Storage)

Two variants for compatibility:

#### Linode-style (Path Addressing)

**Default Configuration:**
- Image: `minio/minio`
- Ports: 9000 (API), 9001 (Console)
- Addressing: Path-style (`endpoint/bucket/file`)
- Signature: S3v4

**Installation:**
```bash
vibe-servers install minio
# Select option 1 for Linode-style
```

**Console:**
- URL: `http://localhost:9001`
- Credentials: `minioadmin` / `minioadmin`

#### AWS-style (Virtual Addressing)

**Default Configuration:**
- Image: `minio/minio`
- Ports: 9010 (API), 9011 (Console)
- Addressing: Virtual-style (`bucket.endpoint/file`)
- Signature: S3v4

**Installation:**
```bash
vibe-servers install minio
# Select option 2 for AWS-style
```

### imgproxy

**Default Configuration:**
- Image: `darthsim/imgproxy:latest`
- Port: 8080

**Usage:**
- On-the-fly image resizing
- Format conversion
- S3 protocol URL support

## Linode Object Storage Compatibility

The local MinIO setup is configured for seamless transition to Linode Object Storage:

### Key Features

- **Path-Style Addressing**: Uses `endpoint/bucket/file` format (standard for Linode)
- **Signature Version**: Enforces `s3v4` authentication
- **Protocol Detection**: Supports both `http` (local) and `https` (production)
- **S3 Protocol URLs**: Overrides default behavior for internal services like `imgproxy`

### Configuration

```json
{
  "s3-linode": {
    "host": "localhost",
    "port": 9000,
    "access_key": "minioadmin",
    "secret_key": "minioadmin",
    "region": "us-east-1",
    "addressing_style": "path",
    "signature_version": "s3v4"
  }
}
```

## Infrastructure Specification

### Managing Infrastructure Spec

The infrastructure specification is managed through:

1. **Markdown spec**: `specs/infrastructure.md`
2. **Normalized YAML**: `project/prds/infrastructure.yaml`
3. **Current state**: `project/infrastructure-current.yaml`

### Updating Infrastructure

**Via Interactive Tool:**
```bash
vibe architect
# Use /show infra to view
# Use /agent mode to update
```

**Via Normalization:**
```bash
# Edit specs/infrastructure.md
vibe normalize infrastructure
```

### Reconciliation

Infrastructure reconciliation ensures the actual infrastructure matches the spec:

```bash
vibe infra
```

This runs a reconciliation loop comparing:
- Desired: `project/prds/infrastructure.yaml`
- Current: `project/infrastructure-current.yaml`

## Service Verification

**Test all configured services:**
```bash
vibe-setup test
```

This verifies connectivity for all configured services and reports:
- Connection status
- Configuration issues
- Missing services

## Global Server Configuration

Server configurations can be stored globally in `~/.vibe/servers.json`:

```json
{
  "postgres": {
    "container_name": "vibe-postgres",
    "ports": {"5432/tcp": 5432}
  }
}
```

This allows:
- Shared configurations across projects
- Default server settings
- Consistent development environments

## Best Practices

### Service Management

1. **Use Docker containers**: Consistent across team
2. **Configure via vibe-setup**: Ensures proper format
3. **Test connectivity**: Use `vibe-setup test`
4. **Version control config**: Commit non-sensitive config

### Infrastructure Spec

1. **Keep spec updated**: Reflect actual infrastructure
2. **Use reconciliation**: Ensure code matches spec
3. **Document changes**: Update spec when infrastructure changes
4. **Test locally first**: Verify with local servers

### Production Transition

1. **Match local to production**: Use same addressing styles
2. **Test compatibility**: Verify S3 compatibility
3. **Update endpoints**: Change host/port for production
4. **Secure credentials**: Use environment variables

## Troubleshooting

### Service Won't Start

**Check container status:**
```bash
docker ps -a
vibe-servers status
```

**View logs:**
```bash
vibe-servers logs <service>
docker logs <container_name>
```

**Recreate container:**
```bash
vibe-servers remove <service>
vibe-servers install <service>
```

### Connection Issues

**Verify configuration:**
```bash
vibe-setup test
vibe status
```

**Check ports:**
```bash
vibe-servers status
# Verify ports are not in use
```

**Test connectivity:**
```bash
# PostgreSQL
psql -h localhost -p 5432 -U postgres

# Redis
redis-cli -h localhost -p 6379

# Elasticsearch
curl http://localhost:9200
```

### Configuration Problems

**Reset configuration:**
```bash
# Remove from config
# Edit project/config.json manually
# Or reconfigure:
vibe-setup <service>
```

**Check Docker:**
```bash
docker ps
docker inspect <container_name>
```

See [Troubleshooting](12-troubleshooting.md) for more help.
