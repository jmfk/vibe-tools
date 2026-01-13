# Project Structure

## Overview
- **Problem statement**: Projects need a standardized directory structure for specs, PRDs, prompts, project state, logs, and costs. The structure must support both human-written specs and machine-readable PRDs, version control, and easy navigation.
- **User benefits**: Consistent project layout across all vibe-tools projects, clear separation of concerns, easy discovery of files, and support for both human and machine workflows.
- **Success criteria**: Standard directory structure created automatically, supports all workflow types, integrates with git, and provides clear file organization.

## Feature Inspiration
The project structure defines standard directories for different types of content: `specs/` for human-written markdown specifications, `implementation/prds/` for machine-readable YAML PRDs, `prompts/` for AI prompt templates, `implementation/` for state files and logs, and `instructions/` for global agent instructions. The structure supports both new projects and adoption of existing codebases.

**Key directories**:
- `specs/`: Human-written markdown specs (architecture.md, infrastructure.md, etc.)
- `implementation/prds/`: Machine-readable YAML PRDs (prd_*.yaml, architecture.yaml, etc.)
- `implementation/logs/`: Command-specific log files
- `implementation/costs/`: Cost tracking CSV files
- `prompts/`: AI prompt templates
- `instructions/`: Global agent instructions
- `implementation/`: Session state files, current state YAMLs

## Frontend
N/A - Directory structure only.

## Backend
- **Directory Creation**: `ensure_dir()` function creates directories with proper permissions, handles existing directories gracefully.
- **Standard Directories**:
  - `specs/`: Markdown specifications (user-created)
  - `implementation/prds/`: YAML PRDs (generated from specs)
  - `implementation/logs/`: Log files (auto-created per command)
  - `implementation/costs/`: Cost CSV files (auto-created)
  - `prompts/`: Prompt templates (from package or project)
  - `instructions/`: Global instructions (user-created)
  - `implementation/`: State files (auto-managed)
- **File Organization**:
  - Specs: `specs/*.md` (architecture.md, infrastructure.md, cicd.md, testing.md, prd_*.md)
  - PRDs: `implementation/prds/prd_*.yaml` (implementation PRDs), `implementation/prds/*.yaml` (global truths)
  - Logs: `implementation/logs/{command_name}.log`
  - Costs: `implementation/costs/usage.csv`
  - State: `implementation/{name}-session.json`, `implementation/{name}-current.yaml`
- **Git Integration**: `.gitignore` automatically updated to exclude logs, costs, and state files (but include specs and PRDs).
- **Template System**: Templates can be initialized from package or project-specific versions.

## Infrastructure
- **File System**: Standard POSIX file system, supports symlinks for templates.
- **Permissions**: Directories created with user's default permissions (typically 755).
- **Version Control**: Structure designed for git, with appropriate files in `.gitignore`.
- **Migration**: Supports migration from legacy directory structures (e.g., `prds/` to `implementation/prds/`).

## Architecture and Constraints
- **Separation of Concerns**: Human specs separate from machine PRDs, state files separate from source files.
- **Naming Conventions**: Consistent naming (specs use `.md`, PRDs use `.yaml`, logs use command name).
- **Backward Compatibility**: Supports projects with old directory structures via migration.
- **Cross-Platform**: Works on Unix, macOS, and Windows (with pathlib).

## Success Criteria
- All standard directories created on `vibe init`
- Files organized logically and discoverable
- Git integration works correctly
- Migration from old structures successful
- No file conflicts or overwrites

## Acceptance Tests
1. **Initialization**: Run `vibe init`, verify all directories created
2. **Directory Structure**: Verify `specs/`, `implementation/prds/`, `implementation/logs/`, `implementation/costs/` exist
3. **Git Integration**: Verify `.gitignore` includes logs/costs, excludes specs/PRDs
4. **File Creation**: Create spec file, verify appears in correct location
5. **Migration**: Simulate old structure, run init, verify migration successful
6. **Permissions**: Verify directories have correct permissions
7. **Template Loading**: Verify templates load from correct location (package vs project)

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-003
title: Project Structure
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.011138'
updated_at: '2026-01-13T20:31:39.752701'
discussion_id: D_kwDOQzI0Lc4AjoSW
discussion_url: https://github.com/jmfk/vibe-tools/discussions/28
last_synced_at: '2026-01-13T20:31:39.752593'
sync_hash: b7d972350d36ddcd32f4e205cd6aecdddf0f7696566f9ccd28720461ede1587b
implementation_id: v01-060
implementation_yaml: v01-060_03_project_structure.yaml
issue_number: null
```
</details>

<!-- vibe-id: PRD-003 -->
