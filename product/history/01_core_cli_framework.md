---
discussion_id: D_kwDOQzI0Lc4AjltK
discussion_url: https://github.com/jmfk/vibe-tools/discussions/23
last_synced_at: '2026-01-10T15:24:13.401810'
sync_hash: 5fbfbfe9d74e1412b42743f483288ac0b7d8af70b682539e6e817e1caa5690be
---

# Core CLI Framework

## Overview
- **Problem statement**: Developers need a unified, extensible command-line interface to access all vibe-tools functionality. The CLI must support multiple commands, provide consistent help and error handling, manage global configuration, and integrate with various AI agents and workflows.
- **User benefits**: Single entry point (`vibe`) for all tooling, consistent UX across commands, easy command discovery via help system, flexible agent selection, and centralized configuration management.
- **Success criteria**: CLI supports 30+ commands, provides comprehensive help, handles errors gracefully, supports multiple agent backends, and maintains backward compatibility.

## Feature Inspiration
The CLI framework provides the foundation for all vibe-tools commands. It uses Click for command registration and parsing, supports ordered command groups for logical organization, and provides global options (debug, verbose, stream, agent selection, caffeinate) that apply to all subcommands. The framework initializes logging, loads configuration, registers exit handlers for cost reporting, and ensures proper project directory structure.

**Key capabilities**:
- Command registration and discovery
- Global option handling (debug, verbose, stream, agent, caffeinate)
- Configuration loading and validation
- Logging initialization per command
- Session cost tracking and reporting
- Project directory migration and setup

## Frontend
N/A - CLI-only interface.

## Backend
- **Command Registration System**: Uses Click's Group and Command decorators. Custom `OrderedGroup` class ensures commands appear in logical order in help output.
- **Global Options**:
  - `--debug`: Enable debug logging to console
  - `--verbose/--no-verbose`: Control verbose output (default: True)
  - `--stream/--no-stream`: Stream agent output in real-time
  - `--agent`: Select agent backend (cursor-agent, claude, antigravity)
  - `--caffeinate`: Prevent system sleep during long tasks
- **Configuration Management**: Loads `.vibe_config.json` from project root, merges with defaults, validates required fields.
- **Logging System**: Per-command logging setup, console and file handlers, configurable log levels based on verbose/debug flags.
- **Cost Tracking Integration**: Registers atexit handler to finalize cost reports, tracks session costs across all commands.
- **Project Initialization**: Ensures `project/` directory exists, migrates legacy files, validates git repository.

## Infrastructure
- **Deployment**: Python package installable via pip, entry points defined in `setup.py`/`pyproject.toml`.
- **Dependencies**: Click (CLI framework), python-dotenv (environment variables), standard library (logging, pathlib, atexit).
- **Configuration Storage**: `.vibe_config.json` in project root (user-editable, git-ignored by default).
- **Logging Storage**: Command-specific log files in `project/logs/` directory.

## Architecture and Constraints
- **Modular Design**: Commands registered via `register_all_commands()` function, allowing easy addition of new commands.
- **Command Ordering**: Commands grouped by phase (architect, pm, normalize, setup, deps, implement, build, run, etc.) followed by supporting tools.
- **Agent Abstraction**: Agent selection abstracted, allowing multiple backends (Cursor Agent, Claude, Antigravity) with consistent interface.
- **Error Handling**: Graceful degradation when config files missing, validation errors logged but don't crash.
- **Backward Compatibility**: Must support existing command syntax, configuration formats, and project structures.

## Success Criteria
- All 30+ commands accessible via `vibe --help`
- Commands appear in logical order
- Global options work consistently across all commands
- Configuration loads correctly with sensible defaults
- Logging works for all commands
- Cost tracking integrates seamlessly
- Zero crashes on missing config files

## Acceptance Tests
1. **Command Discovery**: Run `vibe --help` and verify all commands listed in correct order
2. **Global Options**: Run `vibe status --debug --verbose --agent claude` and verify options applied
3. **Configuration Loading**: Create minimal `.vibe_config.json`, run any command, verify config loaded
4. **Missing Config**: Delete `.vibe_config.json`, run command, verify graceful handling with defaults
5. **Logging**: Run command with `--debug`, verify debug logs appear in console and log file
6. **Cost Tracking**: Run multiple commands, verify session cost report at exit
7. **Command Execution**: Run each major command category, verify no framework-related errors