# Rerun System

## Overview
- **Problem statement**: When PRD implementation fails or needs to be redone, developers need a way to reset the PRD state and rerun it from scratch. The system should reset state, clear branches, and allow fresh implementation attempts.
- **User benefits**: Easy PRD reruns, state reset, and fresh implementation attempts.
- **Success criteria**: `vibe rerun` successfully resets PRD state, clears implementation state, and allows rerunning PRDs.

## Feature Inspiration
The `vibe rerun <prd_id>` command resets a PRD's implementation state, allowing it to be rerun from scratch. It clears state files, resets branch status, and prepares for a fresh implementation attempt.

**Key capabilities**:
- PRD state reset
- Branch status reset
- Implementation state clearing
- Fresh rerun preparation

## Frontend
N/A - CLI command.

## Backend
- **Rerun Process**:
  1. Validate PRD ID exists
  2. Reset PRD state in project state
  3. Clear implementation state for PRD
  4. Reset branch status (if applicable)
  5. Prepare for fresh implementation
- **State Reset**: 
  - `reset_prd_state(prd_id)`: Resets PRD state
  - Clears status, iterations, completion flags
  - Resets to "pending" status
- **Branch Handling**: 
  - May reset branch status
   - May delete or reset branch (optional)
- **Validation**: 
  - Checks PRD exists
  - Validates PRD ID format
  - Provides helpful error messages

## Infrastructure
- **State Files**: Modifies project state files.
- **Git**: May interact with git for branch reset.

## Architecture and Constraints
- **State Safety**: Reset should be safe, not lose important data.
- **Branch Safety**: Branch reset should be optional or safe.

## Success Criteria
- PRD state reset correctly
- Implementation state cleared
- Rerun works after reset
- Validation works

## Acceptance Tests
1. **State Reset**: Rerun PRD, verify state reset
2. **Implementation Clear**: Verify implementation state cleared
3. **Rerun**: Rerun PRD after reset, verify works
4. **Validation**: Test with invalid PRD ID, verify error

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-026
title: Rerun System
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.014073'
updated_at: '2026-01-13T20:07:27.802538'
discussion_id: null
discussion_url: https://github.com/jmfk/vibe-tools/discussions/39
last_synced_at: null
sync_hash: null
issue_number: null
```
</details>

<!-- vibe-id: PRD-026 -->
