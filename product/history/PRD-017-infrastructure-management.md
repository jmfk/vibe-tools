# Infrastructure Management

## Overview
- **Problem statement**: Projects need to manage infrastructure specifications that define deployment targets, monitoring, storage, and operational requirements. The system should support interactive refinement and integration with the implementation workflow.
- **User benefits**: Interactive infrastructure spec management, integration with architect shell, and automated infrastructure setup.
- **Success criteria**: Infrastructure management successfully maintains infrastructure specs, integrates with architect shell, and supports infrastructure implementation.

## Feature Inspiration
The `vibe infra` command manages infrastructure specifications. It integrates with the architect shell to refine `SRD-infrastructure.md`, converts it to YAML for machine processing, and supports infrastructure implementation via the Ralph loop.

**Key capabilities**:
- Infrastructure spec management
- Integration with architect shell
- YAML conversion for machine processing
- Infrastructure implementation support

## Frontend
N/A - CLI command, integrates with architect shell.

## Backend
- **Spec File**: `specs/SRD-infrastructure.md` (human-written markdown).
- **YAML Conversion**: Converts to `implementation/prds/infrastructure.yaml` (global truth).
- **Architect Integration**: Can be refined via `vibe architect` shell.
- **Implementation**: Infrastructure can be implemented via Ralph loop:
  - Desired: `infrastructure.yaml`
  - Current: Actual infrastructure state
  - Loop reconciles desired vs actual
- **Content**: Infrastructure specs typically include:
  - Primary services (databases, caches, queues)
  - External integrations (APIs, third-party services)
  - Environment management (dev, staging, prod)
  - Deployment targets
  - Local orchestration (Docker, etc.)

## Infrastructure
- **Spec Storage**: `specs/SRD-infrastructure.md`.
- **YAML Storage**: `implementation/prds/infrastructure.yaml`.
- **Integration**: Works with architect shell and Ralph loop.

## Architecture and Constraints
- **Global Truth**: Infrastructure is a global truth, injected into all agent prompts.
- **Spec Format**: Markdown for humans, YAML for machines.
- **Implementation**: Infrastructure implementation may require manual steps or external tools.

## Success Criteria
- Infrastructure specs manageable
- Architect integration works
- YAML conversion successful
- Implementation support works

## Acceptance Tests
1. **Spec Management**: Create/edit SRD-infrastructure.md, verify saved
2. **Architect Integration**: Use architect shell, verify infrastructure spec accessible
3. **YAML Conversion**: Normalize SRD-infrastructure.md, verify YAML created
4. **Global Truth**: Verify infrastructure.yaml included in agent context
5. **Implementation**: Run infrastructure implementation loop, verify works

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-017
title: Infrastructure Management
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.010310'
updated_at: '2026-01-17T22:40:12.089986'
discussion_id: null
discussion_url: https://github.com/jmfk/vibe-tools/discussions/26
last_synced_at: null
sync_hash: null
issue_number: null
```
</details>

<!-- vibe-id: PRD-017 -->
