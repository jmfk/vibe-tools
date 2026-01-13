# Process Management

## Overview
- **Problem statement**: Developers need to monitor and manage running processes (agent processes, pytest, caffeinate) to avoid resource leaks and manage long-running tasks. The system should provide process listing and cleanup capabilities.
- **User benefits**: Process visibility, resource management, and easy cleanup of stale processes.
- **Success criteria**: `vibe ps` and `vibe kill` successfully list and manage processes, and cleanup works correctly.

## Feature Inspiration
The `vibe ps` and `vibe kill` commands provide process management. They identify running agent processes, pytest processes, and caffeinate processes, allow listing them, and provide cleanup capabilities.

**Key capabilities**:
- Process detection (agents, pytest, caffeinate)
- Process listing
- Process cleanup
- Stale process detection

## Frontend
N/A - CLI commands.

## Backend
- **Process Detection**: 
  - `get_agent_processes()`: Finds running agent processes
  - Detects pytest processes
  - Detects caffeinate processes
  - Uses process name/command matching
- **PS Command** (`vibe ps`):
  - Lists all detected processes
  - Shows process ID, command, status
  - Formatted table output
- **Kill Command** (`vibe kill`):
  - Kills specified processes
  - `--yes` flag for confirmation
  - `vibe kill all`: Kills all detected processes
- **Cleanup Function**: 
  - `cleanup_stale_processes()`: Automatically cleans stale processes
  - Called by other commands
  - Detects and kills orphaned processes

## Infrastructure
- **Process Management**: Uses system process APIs (ps, kill).
- **Process Detection**: Command-line matching, process tree traversal.

## Architecture and Constraints
- **Platform Support**: Process detection varies by platform.
- **Safety**: Kill commands should be safe, avoid killing wrong processes.

## Success Criteria
- Processes detected correctly
- Process listing accurate
- Process cleanup works
- Stale process detection reliable

## Acceptance Tests
1. **Process Detection**: Run processes, verify detected
2. **Process Listing**: Run `vibe ps`, verify processes shown
3. **Process Cleanup**: Kill processes, verify terminated
4. **Stale Detection**: Test stale process detection, verify works

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-030
title: Process Management
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.015681'
updated_at: '2026-01-13T23:56:53.401672'
discussion_id: null
discussion_url: https://github.com/jmfk/vibe-tools/discussions/45
last_synced_at: null
sync_hash: null
issue_number: null
```
</details>

<!-- vibe-id: PRD-030 -->
