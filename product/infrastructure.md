---
discussion_id: D_kwDOQzI0Lc4AjlwI
discussion_url: https://github.com/jmfk/vibe-tools/discussions/72
---

# Infrastructure Specification

## 1. Overview
The infrastructure is designed to be reliable and scalable, prioritizing standard tools that are easy to run locally via Docker and easy to deploy to cloud providers via Kubernetes and Terraform.

## 2. Local Development Services
All infrastructure components have a corresponding Docker-based setup for local development, managed via the unified `vibe` CLI.

### 2.1 Database & Storage
- **Postgres**: Primary relational database, using `pgvector/pgvector:pg16` for vector search capabilities.
- **Redis**: In-memory data store for caching and session management.
- **MinIO**: S3-compatible object storage (available in both Linode and AWS addressing styles).

### 2.2 Messaging & Search
- **RabbitMQ**: Message broker for asynchronous task management.
- **Elasticsearch**: Distributed search and analytics engine.

### 2.3 Development Tools
- **MailHog**: Email testing tool for capturing and viewing outgoing emails during development.
- **imgproxy**: On-the-fly image resizing and conversion service.

## 3. Cloud Deployment
The project supports sophisticated infrastructure provisioning and deployment to multiple cloud providers.

### 3.1 Kubernetes Clusters
- **Managed K8s**: Automated generation of Terraform configurations for:
    - **AWS EKS**
    - **Linode LKE**
    - **DigitalOcean DOKS**
- **Lightweight K8s (k3s)**: Automated setup for:
    - **Hetzner Cloud**
    - **Bare Metal** servers

### 3.2 Deployment Workflow
- **Terraform**: Used for Infrastructure as Code (IaC) to provision cloud resources.
- **Docker**: Containerization for all application components and services.
- **Kubernetes (k8s)**: Orchestration for container deployment and management.

## 4. Configuration & Environment Management
- **Unified CLI**: The `vibe` command provides a single interface for managing infrastructure:
    - `vibe infra`: General infrastructure management and cloud reconciliation.
    - `vibe setup`: Environment and service configuration.
    - `vibe deploy`: Deployment to target cloud environments.
- **Local Service Management**: Supporting services are managed via `vibe servers`:
    - `vibe servers list`: List available local services.
    - `vibe servers install <service>`: Setup a new local service via Docker.
    - `vibe servers start/stop`: Manage service state.
- **Tiered Configuration**:
    - **Global**: `~/.vibe/config.json` for user-specific settings and credentials.
    - **Project-Level**: `.vibe_config.json` for project-specific infrastructure definitions.
- **Environment Variables**: Managed and populated based on the tiered configuration.