# Spec Management

## Overview
- **Problem statement**: Projects need to manage multiple specification files (architecture, infrastructure, CICD, testing, feature PRDs) with clear separation between human-written specs and machine-readable PRDs. The system must support global truth files that provide context to all agents.
- **User benefits**: Clear organization of specs, automatic context injection for global truths, separation of human and machine formats, and easy discovery of all specifications.
- **Success criteria**: Spec management supports all spec types, global truths properly injected into agent context, specs discoverable and manageable, and clear workflow from specs to PRDs to implementation.

## Feature Inspiration
The spec management system organizes specifications into two categories: human-written markdown specs in `specs/` and machine-readable YAML PRDs in `implementation/prds/`. Global truth files (architecture, infrastructure, CICD, testing, project_overview) are automatically converted to YAML and injected into every agent prompt as context.

**Key capabilities**:
- Spec file organization (markdown in specs/, YAML in implementation/prds/)
- Global truth identification and injection
- Spec discovery and listing
- Context management for agents
- Workflow from specs → PRDs → implementation

## Frontend
N/A - File system organization and CLI commands.

## Backend
- **Spec File Types**:
  - **Global Truths**: `architecture.md`, `infrastructure.md`, `cicd.md`, `testing.md`, `project_overview.md`
    - Converted to: `architecture.yaml`, `infrastructure.yaml`, etc.
    - Injected into every agent prompt as context
  - **Feature PRDs**: `prd_*.md` or `*.md` (other specs)
    - Converted to: `prd_*.yaml`
    - Processed individually by implementation loop
- **Spec Discovery**: `collect_prd_files()` function:
  - Finds all `prd_*.yaml` files in `implementation/prds/`
  - Excludes global truth files
  - Returns sorted list for processing
- **Global Truth Injection**: 
  - Loads global truth YAML files
  - Includes in agent prompt context
  - Provides persistent system state to agents
- **Spec Workflow**:
  1. Human writes markdown spec in `specs/`
  2. `vibe normalize` converts to YAML in `implementation/prds/`
  3. `vibe implement` processes YAML PRDs
  4. Global truths always included as context
- **File Management**: 
  - Specs editable by humans (markdown)
  - PRDs generated automatically (YAML)
  - Both version controlled (typically)

## Infrastructure
- **Spec Storage**: `specs/*.md` files (human-editable).
- **PRD Storage**: `implementation/prds/*.yaml` files (generated).
- **Global Truth Location**: `implementation/prds/{name}.yaml` (no prd_ prefix).

## Architecture and Constraints
- **Separation of Concerns**: Human specs separate from machine PRDs, clear conversion step.
- **Global Truth Persistence**: Global truths must be kept up-to-date, changes require re-normalization.
- **Context Injection**: Global truths always included, ensuring agents have system context.
- **Workflow Enforcement**: Encourages spec → normalize → implement workflow.
- **Version Control**: Both specs and PRDs typically version controlled, allowing history tracking.

## Success Criteria
- All spec types properly organized
- Global truths correctly identified and injected
- Spec discovery works correctly
- Workflow from specs to implementation clear
- Context injection reliable

## Acceptance Tests
1. **Global Truth Identification**: Create architecture.md, normalize, verify architecture.yaml created
2. **Context Injection**: Run agent command, verify global truths in context
3. **Spec Discovery**: Create multiple PRDs, verify all discovered
4. **Workflow**: Write spec, normalize, implement, verify workflow works
5. **File Organization**: Verify specs in specs/, PRDs in implementation/prds/
6. **Global Truth Updates**: Update architecture.md, re-normalize, verify context updated
7. **PRD Processing**: Verify only prd_*.yaml files processed by implement, not global truths

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-007
title: Spec Management
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.017783'
updated_at: '2026-01-13T23:56:53.408389'
discussion_id: null
discussion_url: https://github.com/jmfk/vibe-tools/discussions/53
last_synced_at: null
sync_hash: null
implementation_id: v01-130
implementation_yaml: v01-130_09_spec_management.yaml
issue_number: null
```
</details>

<!-- vibe-id: PRD-007 -->
