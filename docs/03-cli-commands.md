# CLI Commands Reference

## Global Options

All `vibe` commands support these global options:

- `--debug`: Enable debug logging to console
- `--verbose` / `--no-verbose`: Output verbose information (default: verbose)
- `--stream` / `--no-stream`: Stream agent output in real-time (default: no-stream)
- `--agent [cursor-agent|claude|antigravity]`: Select the agent to use (default: cursor-agent)
- `--stream` / `--no-stream`: Stream agent output in real-time
- `--version`: Show version information

## Command Categories

Commands are organized into phases and supporting tools:

### Phase Commands (1-8)

These commands represent the main development lifecycle phases.

#### Phase 1: Architecture & Planning

**`vibe architect [query]`**
- Interactive Architecture & Infrastructure manager
- Preferred tool for system design
- See [Interactive Tools](08-interactive-tools.md) for details
- Options: Inherits global options

**`vibe pm [query]`**
- Interactive PRD & Specification manager
- Preferred tool for requirement gathering
- See [Interactive Tools](08-interactive-tools.md) for details
- Options: Inherits global options

#### Phase 2: Normalization

**`vibe normalize [input_files...]`**
- Normalize human-written PRDs from `product/` into machine-consumable YAML in `prds/`
- Options:
  - `--yes, -y`: Automatically overwrite existing PRDs
  - `--debug`: Output all prompts and results for debugging
- Examples:
  ```bash
  vibe normalize                    # Normalize all specs
  vibe normalize infrastructure     # Normalize specific spec
  vibe normalize product/01_feature.md
  ```

#### Phase 3: Setup

**`vibe setup [--import-code]`**
- Architecture Setup reconciliation
- Ensures project structure matches architecture spec
- Options:
  - `--import-code`: Import existing codebase during setup

**`vibe-setup <option>`**
- Configure tool settings and API keys
- Options: `api`, `google`, `test`
- Examples:
  ```bash
  vibe-setup api
  vibe-setup test  # Verify configuration
  ```

#### Phase 4: Dependencies

**`vibe deps`**
- Install required Python and Frontend dependencies
- Reads dependency requirements from project configuration

#### Phase 5: Implementation

**`vibe implement`**
- Execute implementation phase based on PRD plans in `state.json`
- Runs reconciliation loops for architecture, infrastructure, CI/CD, testing, and implementation
- See [Ralph Integration](06-ralph-integration.md) for details

#### Phase 6: Testing

**`vibe testing`**
- Testing reconciliation
- Ensures integration and regression tests pass

### Supporting Tools

#### Status & Monitoring

**`vibe status`**
- Display comprehensive system status report
- Shows: costs, PRDs, servers, logs, configuration

**`vibe usage`**
- Get Cursor usage and cost statistics
- Consolidates cost, stats, and download functionality
- See [Usage Command](13-usage-command.md) for details
- Options:
  - `--download`: Download latest usage data from Cursor API
  - `--report`: Generate a statistics report in `reports/`
  - `--days`, `--month`, `--prev-month`, etc.: Filter by date range

**`vibe history`**
- List the status of all PRDs
- Shows PRD state, branches, and implementation status

**`vibe ps`**
- List active agent processes
- Shows running agent instances

**`vibe kill [--yes]`**
- Kill all active agent processes
- Options:
  - `--yes, -y`: Automatically confirm kill

**`vibe billing-groups`**
- Manage billing groups for cost allocation

#### Documentation

**`vibe docs`**
- Display the project documentation (README.md)
- Shows template README if available

#### Memory & Instructions

**`vibe memory [text] [--list]`**
- Save a global instruction ("memory") always sent to the agent
- Options:
  - `--list, -l`: List all saved memories
- Examples:
  ```bash
  vibe memory "Always use type hints"
  vibe memory --list
  ```

#### PRD Management

**`vibe rerun <prd_id>`**
- Reset a PRD's state and branch to allow rerunning from scratch
- Clears implementation state for the specified PRD

**`vibe implemented`**
- List implemented PRDs (batched) and optionally reset them
- Shows completed PRDs from project state

#### Testing & Coverage

**`vibe coverage`**
- Run the coverage improvement loop
- Iteratively improves test coverage using AI agent
- See [Workflows](09-workflows.md) for details

**`vibe test-fix [--fast]`**
- Run the test and fix loop
- Automatically fixes failing tests
- Options:
  - `--fast, --no-fast`: Only run tests for changed files (default: false)

**`vibe quick-fix [--files FILES]`**
- Quick fix for specific files or issues
- Options:
  - `--files, -f`: Comma-separated list of files to fix

#### Branch Management

**`vibe branch`**
- Branch management operations
- Create and manage feature branches

**`vibe branches`**
- List all local branches and their dependencies
- Shows branch relationships and status

**`vibe branch-resolve`**
- Use the agent to resolve git history/conflicts across the branch stack
- Automatically resolves merge conflicts

#### Initialization

**`vibe init`**
- Interactive guided project initialization
- Sets up project structure, templates, and directories
- Guides through initial setup scenarios

#### Desktop App

**`cargo tauri dev`**
- Run the desktop app in development mode

#### Utility Commands

**`vibe demo-data`**
- Generate or manage demo data for development

## Command Ordering

Commands are displayed in a specific order in help output:

1. Phase commands (architect, pm, normalize, setup, deps, implement, testing)
2. Supporting tools (history, status, cost, stats, docs, memory, rerun, implemented, ps, kill, test-fix, coverage, branch, branches, branch-resolve, billing-groups, demo-data, init)

## Command Dependencies

Many commands check for dependencies before execution:

- `normalize` requires: architecture spec
- `implement` requires: normalized PRDs, setup, dependencies
- `testing` requires: implementation completion

Use `vibe status` to check current phase completion status.

## Getting Help

**View all commands:**
```bash
vibe --help
```

**View command-specific help:**
```bash
vibe <command> --help
```

**View system status:**
```bash
vibe status
```

---

<details>
<summary>Metadata</summary>

```yaml
id: DOC-003
title: CLI Commands Reference
type: DOCUMENTATION
status: active
```

</details>

<!-- vibe-id: DOC-003 -->

## Common Command Patterns

**Complete workflow:**
```bash
vibe init                    # Initialize project
vibe architect              # Define architecture
vibe pm                     # Create PRDs
vibe normalize              # Convert to YAML
vibe setup                  # Setup project structure
vibe deps                   # Install dependencies
vibe implement              # Run implementation
vibe testing                # Run tests
```

**Iterative development:**
```bash
vibe pm                     # Refine PRD
vibe normalize              # Update YAML
vibe implement              # Re-implement
vibe test-fix               # Fix any test failures
```

**Cleanup:**
```bash
vibe kill                   # Stop all agents
vibe ps                     # Check for remaining processes
```
