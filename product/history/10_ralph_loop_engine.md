# Ralph Loop Engine

## Overview
- **Problem statement**: The system needs a core reconciliation engine that compares desired state (from PRDs/specs) with actual state (current codebase) and uses AI agents to close the gap. The engine must support iterative refinement, branch management, and completion detection.
- **User benefits**: Automated reconciliation between desired and actual state, iterative improvement until completion, branch isolation for changes, and clear completion signals.
- **Success criteria**: Engine successfully reconciles desired vs actual state, iterates until completion, manages branches correctly, handles errors gracefully, and provides clear progress feedback.

## Feature Inspiration
The Ralph Loop Engine is the core reconciliation mechanism that drives all implementation loops. It compares a desired state file (YAML PRD or spec) with a current state file (actual implementation), uses an AI agent to identify gaps, and iteratively applies changes until the states match. The engine supports multiple phases (architecture, infrastructure, implementation) and uses completion promises to signal when work is done.

**Key capabilities**:
- Desired vs current state comparison
- Iterative agent-driven reconciliation
- Branch management for isolated changes
- Completion promise detection
- Multi-phase support (architecture, infrastructure, implementation)
- Custom instruction injection
- Git commit integration

## Frontend
N/A - Core engine, used by other commands.

## Backend
- **RalphLoop Class**: Core reconciliation loop implementation:
  - `desired_file`: Path to desired state (YAML PRD or spec)
  - `current_file`: Path to current state (actual implementation)
  - `name`: Loop name (for logging)
  - `agent`: Agent backend to use
  - `branch_name`: Git branch for changes
  - `max_iterations`: Maximum reconciliation attempts
- **Reconciliation Process**:
  1. Compare desired vs current (file hash comparison for sync check)
  2. Prepare reconciliation prompt with desired/current content
  3. Call AI agent with prompt
  4. Agent makes code changes
  5. Check for completion promise (`<promise>DONE</promise>`)
  6. If not complete, repeat
  7. If complete, commit changes
- **Branch Management**: 
  - Switches to dedicated branch before starting
  - Commits changes on branch
  - Supports auto-merge branches if configured
- **Sync Detection**: Uses file hashes to detect if desired and current are already in sync.
- **Mode Detection**: 
  - MIGRATION: Current file exists, needs updating
  - INITIALIZATION: Current file missing, needs creation
- **Custom Instructions**: Supports injecting custom instructions into agent prompts.
- **Completion Promise**: Agent signals completion by including `<promise>DONE</promise>` in output.

## Infrastructure
- **File System**: Reads/writes desired and current state files.
- **Git Integration**: Branch switching, committing changes.
- **Agent Integration**: Calls configured agent backend.
- **Logging**: Comprehensive logging of reconciliation steps.

## Architecture and Constraints
- **Idempotency**: Running same reconciliation multiple times should be safe (sync detection).
- **Iteration Limits**: Max iterations prevent infinite loops, but may need adjustment.
- **Branch Isolation**: Each loop runs on dedicated branch, preventing conflicts.
- **Error Handling**: Graceful handling of agent failures, file errors, git errors.
- **Completion Detection**: Relies on agent including completion promise, may need fallback.

## Success Criteria
- Successfully reconciles desired vs actual state
- Iterates until completion or max iterations
- Branch management works correctly
- Completion detection reliable
- Git commits work properly
- Error handling robust

## Acceptance Tests
1. **Initialization Mode**: Run with missing current file, verify file created
2. **Migration Mode**: Run with existing current file, verify updated correctly
3. **Sync Detection**: Run when files in sync, verify early exit
4. **Iteration**: Run with incomplete state, verify multiple iterations
5. **Completion**: Verify completion promise detection works
6. **Branch Management**: Verify branch created/switched correctly
7. **Git Commits**: Verify changes committed on branch
8. **Error Handling**: Test with invalid files, agent failures, verify graceful handling
9. **Custom Instructions**: Verify custom instructions included in prompts
