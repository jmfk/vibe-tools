---
id: PRD-014
title: Update architecture and infrastructure documentation
type: ISSUE
status: done
group: null
depends_on: []
created_at: '2026-01-10T14:29:20.944749'
updated_at: '2026-01-13T18:55:20.026149'
severity: low
service: ''
summary: ''
github:
  repo: jmfk/vibe-tools
  number: 19
  url: https://github.com/jmfk/vibe-tools/issues/19
sync:
  last_synced_at: '2026-01-10T14:48:18.336954'
  sync_hash: e5671b47c5182873f38d94f6d0414c05dbe9f1b4b6747e25c21b217afde1bfe4
issue_number: 82
last_synced_at: '2026-01-13T18:55:20.025980'
sync_hash: 40069245d5f48d78b3edc4d44ea72b0764e6fb0f6948fea2f4366f26e0ffbe5e
---

# Update architecture and infrastructure documentation

## Summary
The `architecture.md` and `infrastructure.md` documentation files are currently outdated and labeled as "Desired," while the codebase has evolved significantly. Key architectural changes include a shift in directory structure, the introduction of a formal 8-phase lifecycle, and a more comprehensive set of infrastructure services and deployment options.

## Reproduction Steps
Discrepancies can be identified by comparing the current documentation in `product/` with the implementation in `vibe_tools/` and the actual project structure:
1.  Check the directory structure: `architecture.md` refers to `specs/` and `implementation/`, while the project uses `product/` and `implementation/`.
2.  Check the commands: `infrastructure.md` refers to `vibe-setup` and `vibe-servers`, but the primary interface is the unified `vibe` CLI with many subcommands.
3.  Check infrastructure support: `infrastructure.md` only lists Redis and S3, but `vibe_tools/servers.py` and `vibe_tools/infrastructure.py` implement many more services and cloud deployment targets.

## Expected Behavior
The documentation should accurately reflect the current project structure, the 8-phase development lifecycle, the actual tech stack (Python 3.11, dspy), the unified CLI command set, and the full range of supported infrastructure services (both local and cloud).

## Actual Behavior
1.  **Project Structure:** Docs mention `specs/` for PRDs and `implementation/` for YAMLs. The actual project uses `product/` for markdown specifications and `implementation/` for machine-readable state, logs, and normalized PRDs.
2.  **Lifecycle:** The 8-phase lifecycle (`normalize` -> `setup` -> `deps` -> `implement` -> `infra` -> `testing` -> `cicd` -> `deploy`) is the core of the project's operation but is missing from the architecture documentation.
3.  **Command Set:** The unified `vibe` CLI is the main interface, providing commands like `vibe architect`, `vibe pm`, `vibe status`, etc., which are not documented.
4.  **Tech Stack:** Docs specify Python 3.9+. The implementation uses Python 3.11 and relies on `dspy` for LLM orchestration.
5.  **Infrastructure Services:** The docs only mention Redis and S3. The codebase implements Postgres (with pgvector), Redis, RabbitMQ, Elasticsearch, MailHog, MinIO, and imgproxy.
6.  **Cloud Deployment:** The project has sophisticated support for generating Kubernetes clusters via Terraform and k3s for multiple providers (AWS, Linode, Hetzner, DO, Bare Metal), which is entirely missing from the infrastructure documentation.
7.  **Configuration:** Environment management has evolved from simple `.env` files to a tiered JSON configuration system (`.vibe_config.json` and global `~/.vibe/config.json`).

## Acceptance Criteria
- [ ] `product/architecture.md` updated to reflect the 8-phase lifecycle.
- [ ] `product/architecture.md` updated with the correct directory structure (`product/` and `implementation/`).
- [ ] `product/architecture.md` tech stack updated to Python 3.11 and `dspy`.
- [ ] `product/infrastructure.md` updated to include all supported local services (Postgres, RabbitMQ, etc.).
- [ ] `product/infrastructure.md` updated to include cloud deployment capabilities (K8s, Terraform, multiple providers).
- [ ] All command references updated to use the unified `vibe <command>` format.
- [ ] Documentation reflects the actual implementation state, removing or updating "Desired" labels where features are complete.