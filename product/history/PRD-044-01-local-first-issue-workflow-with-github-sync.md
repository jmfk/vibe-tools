# 01 Local First Issue Workflow With Github Sync

## System Contract
- {'LOCAL_FIRST_ISSUE_MANAGEMENT': True}
- {'FILE_BASED_ARTIFACTS': True}
- {'GITHUB_SYNCHRONIZATION_TARGET': True}
- {'DETERMINISTIC_RECONCILIATION': True}
- {'AGENT_CONSUMABLE': True}
- {'NO_SILENT_MERGES': True}
- {'CANONICAL_LOCAL_IDENTITY': True}

## Domain Model
### Issue
  {'id': 'STRING (ISSUE-YYYY-MM-DD-XXX)', 'title': 'STRING', 'status': ['backlog', 'in_progress', 'blocked', 'done'], 'severity': ['low', 'medium', 'high', 'critical'], 'service': 'STRING', 'created_at': 'TIMESTAMP', 'updated_at': 'TIMESTAMP', 'github': {'repo': 'STRING', 'number': 'INTEGER', 'url': 'STRING'}, 'sync': {'last_synced_at': 'TIMESTAMP', 'sync_hash': 'STRING'}, 'body': {'summary': 'STRING', 'reproduction_steps': 'STRING', 'expected_behavior': 'STRING', 'actual_behavior': 'STRING', 'evidence': 'STRING', 'acceptance_criteria': 'STRING', 'investigation_notes': 'STRING', 'solution_notes': 'STRING'}}
### Syncstate
  {'mappings': 'MAP', 'metadata': 'MAP'}
### Statusmapping
  {'backlog': {'github_state': 'open', 'label': []}, 'in_progress': {'github_state': 'open', 'label': 'in-progress'}, 'blocked': {'github_state': 'open', 'label': 'blocked'}, 'done': {'github_state': 'closed', 'label': 'resolved'}}

## Capabilities
### Vibe Issue Sync
  {'description': 'Synchronize local issues with GitHub.', 'options': ['--dry-run', '--full', '--since', '--open-only', '--label'], 'actions': ['pull_new_issues', 'push_local_changes', 'update_metadata', 'detect_conflicts'], 'conflict_handling': ['mark_blocked', 'create_conflict_note', 'require_human_resolution']}
### Vibe Issue Investigate
  {'description': 'Create issues via guided investigation.', 'actions': ['read_logs', 'cluster_errors', 'propose_issues', 'generate_issue_files', 'create_github_issues'], 'rules': ['user_confirmation_required', 'redacted_logs']}
### Vibe Issue Solve
  {'description': 'Resolve issue via agent-driven loop.', 'modes': ['investigate', 'solve'], 'actions': ['read_issue', 'inspect_codebase', 'run_tests', 'modify_code', 'update_notes', 'transition_status', 'close_issue']}
### Agent Interaction
  {'requirements': ['update_updated_at', 'update_status', 'append_notes', 'preserve_evidence', 'preserve_severity_scope']}

## Output Targets
### Directory Structure
  {'issues/backlog/': 'Active issues', 'issues/history/': 'Resolved issues', 'issues/meta/index.json': 'Machine-managed sync state'}
### File Format
  Markdown with YAML frontmatter
### Github Sync
  {'authority_local': ['Title', 'Body', 'Status', 'Labels', 'vibe-bot comments'], 'authority_github': ['External comments', 'Reactions', 'Mentions']}

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-044
title: 01 Local First Issue Workflow With Github Sync
type: ISSUE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:53:26.352431'
updated_at: '2026-01-13T20:07:27.777592'
issue_number: null
last_synced_at: null
sync_hash: null
discussion_id: null
```
</details>

<!-- vibe-id: PRD-044 -->
