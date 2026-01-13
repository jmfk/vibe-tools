# 04 Workflow Enhancements

## System Contract
### Inputs
  - PRD files in project/prds/
  - PRD files in vibe-tools-prds/ (legacy)
  - project/state.json (completed_prds)
  - config.json (editor option)
  - Subcommand (all, inbox, backlog, history, trash)
  - PRD ID or partial name
  - Search term
  - Target folder
### Outputs
  - product/inbox/ directory
  - product/backlog/ directory
  - product/history/ directory
  - product/trash/ directory
  - Moved PRD files
  - CLI list output (paged in batches of 10)
  - Filtered CLI list output
  - External editor process
### Constraints
  - Migration command must be idempotent.
  - Implementation loop processes backlog in alphabetical order (supporting numeric prefixes).
  - vibe i defaults to backlog if no subcommand provided.

## Domain Model
### Prd Statuses
  - {'inbox': 'New, un-triaged PRDs or suggestions.'}
  - {'backlog': 'PRDs planned for implementation.'}
  - {'history': 'Successfully implemented PRDs.'}
  - {'trash': 'Dismissed or irrelevant PRDs.'}
### Configuration Options
  - {'editor': 'cursor, typora, code, vim, etc.'}

## Capabilities
- {'Migration': 'Create product/ status directories and relocate existing PRDs based on state.json and legacy directory existence.'}
- {'Viewing': 'List PRDs in status folders with batch paging (10 items) and filename search filtering.'}
- {'Status Management': 'Move PRDs between status folders by ID/partial name; specialized dismiss shortcut for trash.'}
- {'Editing': 'Open PRD file in configured external editor process.'}
- {'Implementation Integration': 'implementation loop reads from product/backlog/ and moves files to product/history/ upon success.'}

## Output Targets
- product/inbox/
- product/backlog/
- product/history/
- product/trash/
- vibe_tools configuration (config.json)

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-041
title: 04 Workflow Enhancements
type: ISSUE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:53:26.275674'
updated_at: '2026-01-13T23:56:53.390501'
issue_number: null
last_synced_at: null
sync_hash: null
discussion_id: null
```
</details>

<!-- vibe-id: PRD-041 -->
