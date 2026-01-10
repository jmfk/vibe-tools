# Infrastructure Specification (Desired)

## 1. Overview
The infrastructure is designed to be "boring" and reliable, prioritizing standard tools that are easy to run locally via Docker and easy to deploy in production.

## 2. Primary Services

### 2.1 Cache & Queue (Redis)
- **Role**: Session storage, caching, and potentially background task management.
- **Local Dev**: Alpine-based Docker container (`redis:alpine`).

### 2.2 Object Storage (S3)
- **Role**: Storage for user-uploaded content, assets, and backups.
- **Compatibility**: Must support standard S3 API (AWS, Linode, MinIO).
- **Configuration**: Managed via environment variables and `vibe-setup`.

## 3. External Integrations
- **Google Sheets API**: For data synchronization and export tasks.
- **LLM Providers**: Accessed via standard APIs for AI-driven features in `vibe-tools`.

## 4. Environment Management
- **Configuration**: All secrets and environment-specific settings are stored in `.env` (not committed).
- **Tooling**: `vibe-setup` provides an interactive way to configure these services and verify connectivity.

## 5. Deployment & Local Orchestration
- **Containers**: All infrastructure components must have a corresponding Docker-based setup for local development.
- **Vibe Servers**: The `vibe-servers` command manages the lifecycle of these local containers, ensuring a consistent developer experience.
