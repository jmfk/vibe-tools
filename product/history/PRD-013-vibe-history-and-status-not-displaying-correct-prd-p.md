---
id: PRD-013
title: Vibe history and status not displaying correct PRD progress
type: ISSUE
status: done
group: null
depends_on: []
created_at: '2026-01-10T17:17:22Z'
updated_at: '2026-01-13T18:58:10.372403'
severity: medium
service: unknown
summary: ''
github:
  repo: jmfk/vibe-tools
  number: 1
  url: https://github.com/jmfk/vibe-tools/issues/1
sync:
  last_synced_at: '2026-01-10T17:17:22Z'
  sync_hash: 2414ba827f679f3b4a259a776ce61cf779b6e19102658482c6d0ebcfd0ad63ba
issue_number: 80
last_synced_at: '2026-01-13T18:53:34.699267'
sync_hash: 96a8728b0977d66e7eb58632110230988cfb77c212e2b8150e07ef8a54219676
---

# Vibe history and status not displaying correct PRD progress

## Summary
The `vibe history` and `vibe status` commands provide inconsistent views of PRD progress. The primary issues are that `started_prds` is not being updated during implementation, naming conventions for PRD IDs are inconsistent between the filesystem and `state.json`, and the `vibe status` report lacks a high-level summary of PRD and Issue progress. Additionally, the `vibe migrate` command is too simplistic and does not reconcile the project state with the actual filesystem or git branch state, which should be the primary mechanism for repairing "broken" history.

## Reproduction Steps
1. Create a new PRD in `specs/` (e.g., `specs/PRD-99-test.md`).
2. Run `vibe normalize` to generate a YAML PRD in `product/prds/backlog/` (e.g., `product/prds/backlog/prd_99_test.yaml`).
3. Run `vibe implement` to start working on the PRD.
4. Observe `vibe history`: The PRD shows as `⚪️ PENDING` even while implementation is running (because `started_prds` is never updated in `vibe_tools/ralph.py`).
5. Observe `vibe status`: While "Implementation Plans" shows the specific plan status, there is no high-level summary of total PRDs/Issues and their progress.
6. Manually move a PRD file from `backlog` to `history` or delete an entry from `state.json`.
7. Run `vibe migrate`: The command does not detect that the file location and `state.json` are out of sync, nor does it offer to update `state.json`.

## Expected Behavior
- **`state.json` as Source of Truth**: All status displays should prioritize `state.json`.
- **Automatic Registration**: `vibe implement` should automatically add the PRD/Plan ID to `started_prds` in `state.json` when starting.
- **`vibe status` Summary**: The status report should include a concise summary of PRD and Issue progress (e.g., "PRDs: 5 Total (2 Done, 1 In Progress, 2 Pending)").
- **Repair via `migrate`**: The `vibe migrate` command should reconcile `state.json` with the filesystem. If a PRD file is found in `history/`, it should ensure it is in `completed_prds`. If found in `backlog/` but a feature branch exists, it should warn the user or suggest marking as `started_prds`.

## Actual Behavior
- **Missing Updates**: `started_prds` is never updated by the implementation loop.
- **Incomplete Status**: `vibe status` shows granular implementation plans but lacks a high-level "Source of Truth" summary for all PRDs and Issues.
- **Simplistic Migration**: `vibe migrate` only moves legacy files to new directories based on existing (and potentially broken) state; it does not perform bidirectional reconciliation or repair `state.json`.

## Acceptance Criteria
- [ ] **Registration**: `vibe_tools/ralph.py` updates `started_prds` in `state.json` when starting an implementation plan.
- [ ] **Summary Display**: `vibe_tools/utils.py:get_vibe_status_report` includes a high-level summary of PRDs and Issues (Total, Done, In Progress, Pending).
- [ ] **Enhanced Migration**: `vibe_tools/commands/migrate.py` is updated to:
    - Reconcile `state.json` based on PRD file locations (`backlog/` vs `history/`).
    - Detect and warn about inconsistencies (e.g., PRD in `history/` but not in `completed_prds`).
    - Check for active git branches (`feature/*`) and suggest updating `started_prds` if a matching PRD is currently `PENDING`.
- [ ] **Consistency**: `vibe history` and `vibe status` use the same ID mapping logic and both reflect `IN_PROGRESS` correctly based on `started_prds`.

## Solution Notes
- Agent started solve mode at 2026-01-10T14:10:35.551973
- Agent started solve mode at 2026-01-10T18:17:21.682129