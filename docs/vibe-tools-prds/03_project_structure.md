# Project Structure

## Overview
- **Problem statement**: Projects need a standardized directory structure for specs, PRDs, prompts, project state, logs, and costs. The structure must support both human-written specs and machine-readable PRDs, version control, and easy navigation.
- **User benefits**: Consistent project layout across all vibe-tools projects, clear separation of concerns, easy discovery of files, and support for both human and machine workflows.
- **Success criteria**: Standard directory structure created automatically, supports all workflow types, integrates with git, and provides clear file organization.

## Feature Inspiration
The project structure defines standard directories for different types of content: `specs/` for human-written markdown specifications, `project/prds/` for machine-readable YAML PRDs, `prompts/` for AI prompt templates, `project/` for state files and logs, and `instructions/` for global agent instructions. The structure supports both new projects and adoption of existing codebases.

**Key directories**:
- `specs/`: Human-written markdown specs (architecture.md, infrastructure.md, etc.)
- `project/prds/`: Machine-readable YAML PRDs (prd_*.yaml, architecture.yaml, etc.)
- `project/logs/`: Command-specific log files
- `project/costs/`: Cost tracking CSV files
- `prompts/`: AI prompt templates
- `instructions/`: Global agent instructions
- `project/`: Session state files, current state YAMLs

## Frontend
N/A - Directory structure only.

## Backend
- **Directory Creation**: `ensure_dir()` function creates directories with proper permissions, handles existing directories gracefully.
- **Standard Directories**:
  - `specs/`: Markdown specifications (user-created)
  - `project/prds/`: YAML PRDs (generated from specs)
  - `project/logs/`: Log files (auto-created per command)
  - `project/costs/`: Cost CSV files (auto-created)
  - `prompts/`: Prompt templates (from package or project)
  - `instructions/`: Global instructions (user-created)
  - `project/`: State files (auto-managed)
- **File Organization**:
  - Specs: `specs/*.md` (architecture.md, infrastructure.md, cicd.md, testing.md, prd_*.md)
  - PRDs: `project/prds/prd_*.yaml` (implementation PRDs), `project/prds/*.yaml` (global truths)
  - Logs: `project/logs/{command_name}.log`
  - Costs: `project/costs/usage.csv`
  - State: `project/{name}-session.json`, `project/{name}-current.yaml`
- **Git Integration**: `.gitignore` automatically updated to exclude logs, costs, and state files (but include specs and PRDs).
- **Template System**: Templates can be initialized from package or project-specific versions.

## Infrastructure
- **File System**: Standard POSIX file system, supports symlinks for templates.
- **Permissions**: Directories created with user's default permissions (typically 755).
- **Version Control**: Structure designed for git, with appropriate files in `.gitignore`.
- **Migration**: Supports migration from legacy directory structures (e.g., `prds/` to `project/prds/`).

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
2. **Directory Structure**: Verify `specs/`, `project/prds/`, `project/logs/`, `project/costs/` exist
3. **Git Integration**: Verify `.gitignore` includes logs/costs, excludes specs/PRDs
4. **File Creation**: Create spec file, verify appears in correct location
5. **Migration**: Simulate old structure, run init, verify migration successful
6. **Permissions**: Verify directories have correct permissions
7. **Template Loading**: Verify templates load from correct location (package vs project)
