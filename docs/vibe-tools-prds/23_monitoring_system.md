# Monitoring System

## Overview
- **Problem statement**: Developers need real-time monitoring of long-running loops (coverage, test-fix, implementation). The system should provide live updates, progress indicators, and allow monitoring multiple loops simultaneously.
- **User benefits**: Real-time loop monitoring, progress tracking, multi-loop support, and clear status updates.
- **Success criteria**: `vibe monitor` successfully monitors loops, provides real-time updates, shows progress clearly, and handles multiple loops.

## Feature Inspiration
The `vibe monitor` command provides real-time monitoring of running loops. It polls loop state files, displays progress, shows current iteration, and updates the display periodically. It can monitor multiple loops simultaneously and provides clear status indicators.

**Key capabilities**:
- Real-time loop monitoring
- Progress indicators
- Multi-loop support
- Periodic updates
- Status indicators (running, completed, failed)

## Frontend
N/A - CLI with live-updating display.

## Backend
- **Monitoring Loop**: 
  - Polls loop state files periodically (default: 2 seconds)
  - Reads state from `implementation/{loop-name}-current.yaml` or state files
  - Updates display with current status
- **State Detection**:
  - Checks for running loops (process detection, state files)
  - Reads iteration count, current phase, status
  - Detects completion (success or failure)
- **Display Format**:
  - Shows loop name
  - Shows current iteration / max iterations
  - Shows current phase
  - Shows status (running, completed, failed)
  - Shows progress bar or percentage
- **Multi-Loop Support**:
  - Can monitor multiple loops simultaneously
  - Shows all loops in single display
  - Updates all loops in real-time
- **Update Interval**: 
  - Configurable via `--interval` flag
  - Default: 2 seconds
  - Balances responsiveness vs CPU usage

## Infrastructure
- **State Files**: Reads from `implementation/` directory.
- **Process Detection**: May check for running processes.
- **Display**: Terminal-based, uses ANSI codes for updates.

## Architecture and Constraints
- **Polling**: Polls files periodically, adds some latency.
- **Terminal Compatibility**: ANSI codes may not work in all terminals.
- **Performance**: Must be lightweight, not impact loop performance.

## Success Criteria
- Real-time updates work
- Progress shown accurately
- Multi-loop support works
- Display clear and readable
- Low CPU impact

## Acceptance Tests
1. **Monitoring**: Start loop, run monitor, verify updates shown
2. **Progress**: Verify progress indicators accurate
3. **Multi-Loop**: Monitor multiple loops, verify all shown
4. **Completion**: Verify completion detected correctly
5. **Update Interval**: Test different intervals, verify updates work
6. **Display**: Verify display clear and readable
