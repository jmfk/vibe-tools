---
id: PRD-043
title: 02 Issue Handling Improvements
type: ISSUE
status: backlog
group: null
depends_on: []
created_at: '2026-01-13T18:53:26.329626'
updated_at: '2026-01-13T18:58:10.362988'
issue_number: 10
last_synced_at: '2026-01-13T18:53:42.841831'
sync_hash: 1f6319ce0ab38bacb738fd4e41149aaa4840e9a90b6aff44128743bd5268e4fb
---

# 02 Issue Handling Improvements

## System Contract
### Commands
  - vibe issue list
  - vibe issue ls
  - vibe issue add
### Arguments List
  - {'--status': ['backlog', 'in_progress', 'blocked', 'done']}
  - {'--severity': ['low', 'medium', 'high', 'critical']}
  - {'--service': 'service name'}
  - {'search': 'positional argument or --search flag (title or body content)'}
  - {'display': '--full or -v'}
### Arguments Add
  - {'prompt': 'positional string argument'}
  - {'--title': 'explicitly set title'}
  - {'--severity': 'explicitly set severity'}
  - {'--service': 'explicitly set service'}
### Data Locations
  - issues/backlog/
  - issues/history/
### Components
  - vibe_tools/issues.py (Issue dataclass, load_index, save_issue)
  - vibe_tools/commands/issue.py
  - vibe_tools/commands/issue_list.py
  - vibe_tools/commands/issue_add.py
  - LLM/Agent logic
  - issue_add_prompt.txt

## Domain Model
### Issue
  {'FIELDS': ['ID', 'Title', 'Status', 'Severity', 'Service', 'Summary', 'Body'], 'STATUS_OPTIONS': ['backlog', 'in_progress', 'blocked', 'done'], 'SEVERITY_OPTIONS': ['low', 'medium', 'high', 'critical']}

## Capabilities
### Listing
  - Show issues from local backlog and history directories
  - Filter by status, severity, and service
  - Search title or body content via regex or substring matching
  - Display concise table view by default
  - Display detailed view via optional flags
### Creation
  - Create issue from single string prompt
  - AI-generation of title, summary, and severity from prompt
  - Support manual overrides for title, severity, and service
  - Direct save of valid Issue artifact to backlog
  - Bypass log analysis and multiple interactive prompts

## Output Targets
### Filesystem
  - issues/backlog/ (Markdown Issue artifacts)
### Cli
  - {'Table View': ['ID', 'Title', 'Status', 'Severity', 'Service']}
  - {'Success Message': ['ID', 'Title', 'Location']}