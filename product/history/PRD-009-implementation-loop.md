# Implementation Loop

## Overview
- **Problem statement**: Developers need an automated way to implement PRDs by running reconciliation loops that transform YAML PRDs into actual code. The process must handle multiple PRDs, dependencies between them, and provide progress tracking.
- **User benefits**: Automated PRD implementation, dependency handling, progress tracking, and integration with the full development workflow.
- **Success criteria**: Implementation loop successfully processes all PRDs, handles dependencies correctly, tracks progress, and produces working implementations.

## Feature Inspiration
The `vibe implement` command runs the implementation loop, which processes all `prd_*.yaml` files in `implementation/prds/` using the Ralph loop engine. It handles PRD dependencies, processes them in order, tracks implementation status, and provides comprehensive progress reporting.

**Key capabilities**:
- PRD discovery and processing
- Dependency resolution and ordering
- Sequential PRD implementation
- Progress tracking
- State management (which PRDs implemented)
- Integration with Ralph loop engine

## Frontend
N/A - CLI command with progress output.

## Backend
- **PRD Discovery**: `collect_prd_files()` finds all `prd_*.yaml` files in `implementation/prds/`.
- **Dependency Resolution**: `check_plan_dependencies()` analyzes PRD dependencies:
  - Reads PRD YAML files
  - Extracts dependency declarations
  - Builds dependency graph
  - Validates no circular dependencies
  - Returns processing order
- **Implementation Process**:
  1. Discover all PRD files
  2. Resolve dependencies, get processing order
  3. For each PRD in order:
     - Create RalphLoop instance
     - Set desired file to PRD YAML
     - Set current file to actual implementation location
     - Run reconciliation loop
     - Track success/failure
  4. Report final status
- **State Tracking**: 
  - Saves implementation state to `implementation/state.json`
  - Tracks which PRDs completed, failed, in progress
  - Used by `vibe implemented` command
- **Progress Reporting**: 
  - Shows current PRD being processed
  - Displays iteration count
  - Reports success/failure per PRD
  - Final summary of all PRDs

## Infrastructure
- **PRD Storage**: `implementation/prds/prd_*.yaml` files.
- **State Storage**: `implementation/state.json`.
- **Implementation Locations**: Determined by PRD (codebase structure).

## Architecture and Constraints
- **Dependency Handling**: Must process PRDs in dependency order, fail fast on circular dependencies.
- **Error Recovery**: Failed PRD doesn't stop entire process, but may affect dependent PRDs.
- **State Persistence**: Implementation state saved between invocations, allows resuming.
- **Integration**: Uses RalphLoop engine for actual reconciliation.

## Success Criteria
- All PRDs discovered correctly
- Dependencies resolved and ordered properly
- PRDs processed in correct order
- Progress tracked accurately
- State persisted correctly
- Failed PRDs handled gracefully

## Acceptance Tests
1. **PRD Discovery**: Create multiple PRDs, verify all discovered
2. **Dependency Resolution**: Create PRDs with dependencies, verify correct order
3. **Circular Dependency**: Create circular dependencies, verify error detected
4. **Sequential Processing**: Verify PRDs processed in dependency order
5. **Progress Tracking**: Verify progress displayed correctly
6. **State Persistence**: Run partial implementation, verify state saved, resume works
7. **Success Tracking**: Verify completed PRDs marked correctly
8. **Failure Handling**: Create failing PRD, verify error handling, other PRDs continue
9. **Integration**: Verify RalphLoop called correctly for each PRD

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-009
title: Implementation Loop
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.018514'
updated_at: '2026-01-13T20:30:39.196846'
discussion_id: D_kwDOQzI0Lc4AjoSI
discussion_url: https://github.com/jmfk/vibe-tools/discussions/55
last_synced_at: '2026-01-13T20:30:39.196722'
sync_hash: 75a00934f8ec08ff277e90987ca804916bf351ff61a28fe5ef9ee7e18acc6199
implementation_id: v01-150
implementation_yaml: v01-150_11_implementation_loop.yaml
issue_number: null
```
</details>

<!-- vibe-id: PRD-009 -->
