---
discussion_id: D_kwDOQzI0Lc4AjltL
discussion_url: https://github.com/jmfk/vibe-tools/discussions/24
last_synced_at: '2026-01-10T15:24:14.797825'
sync_hash: d3b0dad652889d5b35aa3c6792e7d0ea5fbe89ea928e29605e618b9eb5543527
---

# Project Initialization

## Overview
- **Problem statement**: New projects and existing codebases need a guided setup process to initialize vibe-tools directories, templates, and configuration. The process must support multiple starting scenarios (human specs, existing codebase, architecture-ready, manual setup).
- **User benefits**: Fast project onboarding, guided setup for different scenarios, automatic directory creation, template initialization, and codebase discovery for existing projects.
- **Success criteria**: `vibe init` successfully initializes projects in all scenarios, creates required directories, sets up templates, and provides clear next steps.

## Feature Inspiration
The `vibe init` command provides an interactive guided setup process. It presents users with four scenarios: (A) Human Specs - user has markdown specs ready, (B) Adoption - existing codebase to discover, (C) Architecture Ready - has architecture.yaml, (D) Manual Setup - just initialize folders. The command always performs basic initialization (directories, templates, git setup) and then executes scenario-specific steps.

**Key capabilities**:
- Interactive scenario selection
- Basic initialization (directories, templates, git)
- Codebase discovery for existing projects
- Template directory setup
- Git repository validation
- Next steps guidance

## Frontend
N/A - CLI interactive prompts.

## Backend
- **Scenario Selection**: Interactive prompt with four options:
  - **A) Human Specs**: Assumes user has specs in `specs/`, just initializes structure
  - **B) Adoption**: Runs codebase discovery via `vibe setup --import-code`
  - **C) Architecture Ready**: Assumes `architecture.yaml` exists, initializes structure
  - **D) Manual Setup**: Just creates directories and templates
- **Basic Initialization** (`_perform_basic_init()`):
  - Creates standard directories (`specs/`, `implementation/prds/`, `implementation/logs/`, `implementation/costs/`, `instructions/`)
  - Initializes template directory from package templates
  - Sets up `.gitignore` entries
  - Validates git repository (warns if not a git repo)
  - Creates initial `specs/` structure if needed
- **Codebase Discovery**: For scenario B, invokes `vibe setup --import-code` to analyze existing codebase and generate initial specs.
- **Template Initialization**: Copies prompt templates from package to `prompts/` directory (if not exists), allows project-specific overrides.
- **Git Integration**: Checks for git repository, initializes if needed (optional), updates `.gitignore`.

## Infrastructure
- **File System Operations**: Creates directories, copies template files, writes `.gitignore`.
- **Git Operations**: Optional git repository initialization, `.gitignore` updates.
- **Template Storage**: Templates stored in package, copied to project on init.

## Architecture and Constraints
- **Idempotency**: Running `vibe init` multiple times should be safe (doesn't overwrite existing files).
- **User Control**: Users can choose scenario, skip steps, or do manual setup.
- **Backward Compatibility**: Supports projects already using vibe-tools (doesn't break existing structure).
- **Minimal Dependencies**: Basic init requires only file system operations, no external services.

## Success Criteria
- All four scenarios complete successfully
- Directories created correctly
- Templates initialized properly
- Git integration works
- Next steps clearly communicated
- Idempotent (safe to run multiple times)

## Acceptance Tests
1. **Scenario A (Human Specs)**: Select A, verify directories created, no codebase discovery
2. **Scenario B (Adoption)**: Select B, verify codebase discovery runs, initial specs generated
3. **Scenario C (Architecture Ready)**: Select C, verify basic init only
4. **Scenario D (Manual)**: Select D, verify minimal setup
5. **Directory Creation**: Verify all standard directories exist after init
6. **Template Initialization**: Verify templates copied to `prompts/`
7. **Git Integration**: Verify `.gitignore` updated, git repo detected
8. **Idempotency**: Run init twice, verify no errors, no overwrites
9. **Next Steps**: Verify helpful next steps message displayed