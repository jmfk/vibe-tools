---
discussion_id: D_kwDOQzI0Lc4AjltS
discussion_url: https://github.com/jmfk/vibe-tools/discussions/30
last_synced_at: '2026-01-10T15:24:24.458758'
sync_hash: 3830cdc1ac04e0fc45c25fa1947dea8b6582b2645b1bfb7904315a6360b6e01f
---

# Branch Management

## Overview
- **Problem statement**: Projects need Git branch management for PRD implementation, including branch creation, base branch setting, merging, automerge support, and branch status tracking. The system should integrate with the implementation workflow.
- **User benefits**: Automated branch management for PRDs, branch status tracking, dependency-aware branching, automerge support, and branch visualization.
- **Success criteria**: Branch management successfully creates and manages branches, tracks status correctly, handles dependencies, supports automerge, and provides useful branch views.

## Feature Inspiration
The `vibe branch` and `vibe branches` commands provide Git branch management for PRD implementation. Branches are created automatically for each PRD, can have base branches set (for dependencies), support automerge, and provide status tracking and visualization.

**Key capabilities**:
- Branch creation for PRDs
- Base branch setting (dependency support)
- Branch merging
- Automerge support
- Branch status tracking
- Branch visualization (table view)

## Frontend
N/A - CLI commands with formatted output.

## Backend
- **Branch Commands**:
  - `vibe branch base <branch> <base>`: Set base branch for feature branch
  - `vibe branch merge <src> <dst>`: Merge source branch into destination
  - `vibe branch automerge <branch>`: Enable automerge for branch
  - `vibe branch investigate`: Investigate branch status
- **Branches Command** (`vibe branches`):
  - Lists all branches in table format
  - Shows branch, plan ID, status, dependencies, parent branch, merged status
  - Highlights next branch to work on
- **Branch Creation**: 
  - Automatically created by RalphLoop for each PRD
  - Naming: `vibe/{prd_name}` or `feature/{prd_id}`
  - Stored in project state
- **Base Branch Setting**: 
  - Sets parent/base branch for dependency support
  - Stored in `branch_lineage` in project state
  - Used for branch ordering and merging
- **Automerge**: 
  - Configurable per branch or globally
  - Automatically merges to main when PRD complete
  - Requires `auto_merge: true` in config
- **Status Tracking**: 
  - Tracks branch status (pending, in_progress, completed)
  - Tracks merge status (merged into main or not)
  - Updates based on PRD implementation status

## Infrastructure
- **Git Integration**: Uses git commands for branch operations.
- **State Storage**: Branch information in `project/state.json`.

## Architecture and Constraints
- **Git Dependency**: Requires git repository, fails gracefully if not available.
- **Branch Naming**: Consistent naming convention for discoverability.
- **Dependency Handling**: Base branches must exist before setting.

## Success Criteria
- Branches created correctly for PRDs
- Base branch setting works
- Branch merging works
- Automerge functions correctly
- Status tracking accurate
- Branch visualization useful

## Acceptance Tests
1. **Branch Creation**: Implement PRD, verify branch created
2. **Base Branch**: Set base branch, verify stored correctly
3. **Branch Merge**: Merge branches, verify merge successful
4. **Automerge**: Enable automerge, verify merges when complete
5. **Status Tracking**: Verify branch status matches PRD status
6. **Branches View**: Run `vibe branches`, verify table displayed correctly
7. **Dependency Support**: Test branches with dependencies, verify ordering correct