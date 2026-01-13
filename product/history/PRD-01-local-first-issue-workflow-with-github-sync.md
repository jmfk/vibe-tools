# PRD-XX: Local-First Issue Workflow with GitHub Sync

**Project:** vibe-tools
 **Feature:** Issue Management Workflow
 **Status:** Draft
 **Owner:** Core Platform
 **Last updated:** 2026-01-09

------

## 1. Purpose & Motivation

The goal of this feature is to introduce a **local-first, file-based issue management system** that integrates seamlessly with GitHub Issues while remaining usable without GitHub.

The system should:

- Treat issues as **versioned artifacts**, not ephemeral UI objects.
- Allow **AI agents** to reason about, investigate, and solve issues.
- Maintain **deterministic reconciliation** between local files and GitHub.
- Fit naturally into the existing vibe-tools workflow and CLI mental model.

This is **not** a replacement for GitHub Issues. It is a **canonical local representation** with controlled synchronization.

------

## 2. Core Principles

1. **Local files are the primary working surface**
2. **GitHub is a synchronization target, not the source of truth**
3. **Every issue has a stable local identity**
4. **Sync must be deterministic and conflict-safe**
5. **Agents must be able to read, write, and reason over issues**
6. **No silent merges. Ever.**

------

## 3. Directory Structure

The system introduces a new top-level folder:

```
issues/
├── backlog/
│   └── ISSUE-YYYY-MM-DD-XXX-short-slug.md
├── history/
│   └── ISSUE-YYYY-MM-DD-XXX-short-slug.md
└── meta/
    └── index.json
```

### Folder Semantics

- `backlog/`
   Active, open, or unresolved issues.
- `history/`
   Resolved issues. Moving an issue here is a **state transition**, not just archival.
- `meta/index.json`
   Machine-managed sync state and mappings. Never edited manually.

------

## 4. Issue File Format

Each issue is a **single Markdown file** with YAML frontmatter.

### Frontmatter (Required)

```yaml
id: ISSUE-2026-01-09-001
title: Service crashes on startup when cache is cold
status: backlog            # backlog | in_progress | blocked | done
severity: high              # low | medium | high | critical
service: api-gateway
created_at: 2026-01-09T10:12:00Z
updated_at: 2026-01-09T10:12:00Z

github:
  repo: org/repo
  number: 123
  url: https://github.com/org/repo/issues/123

sync:
  last_synced_at: 2026-01-09T10:20:00Z
  sync_hash: abc123
```

### Markdown Body (Structured, but flexible)

Recommended sections:

- Summary
- Reproduction Steps
- Expected Behavior
- Actual Behavior
- Evidence (logs, traces, screenshots)
- Acceptance Criteria
- Investigation Notes
- Solution Notes

Agents are allowed to add sections, but must not remove required ones.

------

## 5. GitHub Sync Model

### Mapping Rules

- One local issue ↔ one GitHub Issue
- Local `id` is canonical
- GitHub issue number is a foreign key

### Source of Truth

| Field                 | Authority          |
| --------------------- | ------------------ |
| Title                 | Local              |
| Body / Description    | Local              |
| Status                | Local              |
| Labels (vibe-managed) | Local              |
| Comments by vibe-bot  | Local              |
| External comments     | GitHub (read-only) |
| Reactions / mentions  | GitHub             |

### Status Mapping

| Local Status | GitHub State | Labels      |
| ------------ | ------------ | ----------- |
| backlog      | open         | —           |
| in_progress  | open         | in-progress |
| blocked      | open         | blocked     |
| done         | closed       | resolved    |

Moving an issue to `history/` **must**:

- close the GitHub issue
- add a resolution label

------

## 6. Sync Behavior (`vibe issue sync`)

### Responsibilities

- Pull new GitHub issues into `backlog/`
- Push local changes to GitHub
- Update metadata and hashes
- Detect conflicts

### Conflict Definition

A conflict exists if:

- Local file changed since last sync **and**
- GitHub issue changed since last sync

### Conflict Handling

- No auto-merge
- Create a conflict note in the issue file
- Mark issue as `status: blocked`
- Require human resolution before next sync

### Sync Modes

- Incremental by default
- Full reindex via `--full`
- Preview via `--dry-run`

------

## 7. CLI Interface

### `vibe issue`

Root command for issue management.

------

### `vibe issue sync`

Synchronize local issues with GitHub.

**Options**

- `--dry-run`
- `--full`
- `--since <date>`
- `--open-only` (default true)
- `--label vibe-managed`

------

### `vibe issue investigate` (`inv`)

Create one or more new issues via guided investigation.

**Behavior**

- Read configured log sources
- Cluster errors by signature
- Propose candidate issues
- Ask clarifying questions
- Generate structured issue files
- Optionally create GitHub issues

**Rules**

- One issue per distinct problem
- User confirmation required before creation
- Logs must be redacted by default

------

### `vibe issue solve`

Attempt to resolve an issue using an agent-driven loop.

**Modes**

- Investigate mode (default)
- Solve mode (after hypothesis convergence)

**Capabilities**

- Read issue file
- Inspect codebase
- Run tests
- Modify code
- Update issue notes
- Transition status
- Close issue when acceptance criteria are met

The command alternates between modes until:

- Issue is resolved
- Issue is blocked
- User aborts

------

## 8. Agent Interaction Contract

Agents must:

- Treat issue files as canonical context
- Update `updated_at` and `status`
- Append investigation and solution notes
- Never delete evidence
- Never silently change severity or scope

------

## 9. Security & Safety

- Secrets must be redacted from logs
- Uploading logs to GitHub is opt-in
- GitHub tokens must be fine-scoped
- No auto-closing without acceptance criteria satisfied

------

## 10. Non-Goals

- Replacing GitHub Issues UI
- Full bidirectional comment editing
- Project management features (boards, sprints)
- SLA or alerting systems

------

## 11. Success Criteria

- Issues can be worked on fully offline
- Sync is deterministic and repeatable
- Conflicts are explicit and visible
- Agents can reliably investigate and solve issues
- No accidental issue loss or silent overwrites

------

## 12. Open Questions

- Should issue templates be configurable per project?
- Should issues be allowed outside GitHub-backed repos?
- Should solved issues be squashed into changelogs automatically?

------

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-01
title: 'PRD-XX: Local-First Issue Workflow with GitHub Sync'
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:37:25.061576'
updated_at: '2026-01-13T20:22:58.569923'
discussion_id: D_kwDOQzI0Lc4AjoRm
discussion_url: https://github.com/jmfk/vibe-tools/discussions/6
last_synced_at: '2026-01-13T20:22:58.569786'
sync_hash: c6298faffd8ce4e57a57e966e483da592447c4eaf0068c34e9315852392aa582
issue_number: null
```
</details>

<!-- vibe-id: PRD-01 -->
