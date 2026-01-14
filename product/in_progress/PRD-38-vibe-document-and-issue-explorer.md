# PRD-38: Vibe Document and Issue Explorer

**Project:** vibe-tools
**Feature:** Planning & Issue Visualization
**Status:** Draft
**Owner:** Core Platform
**Last updated:** 2026-01-13

------

## 1. Purpose & Motivation

This feature provides the visualization layer for the planning and management artifacts of `vibe-tools`. It allows users to browse and edit PRDs, System Specs, and Issues in a structured, rich-text environment.

------

## 2. Core Features

### 2.1 PRD & Spec Browser
- Navigate files in `product/` (inbox, backlog, history).
- Render Markdown with support for:
    - YAML Frontmatter (as a metadata card).
    - Mermaid Diagrams.
    - Code Highlighting.
- Search and filter by status, owner, or text.

### 2.2 System Spec Viewer
- Visualization of files in `implementation/*.yaml` (architecture, cicd, testing).
- Side-by-side view of YAML spec and its corresponding Markdown documentation in `product/`.

### 2.3 Issue Manager
- Interactive list of issues from `issues/`.
- Detail view for individual issues.
- Quick actions: Change status, assign agent, link to PRD.
- Visual timeline of issue updates (investigation notes, solution notes).

------

## 3. Directory Integration

| Artifact | Source Directory | Rendering Mode |
|----------|------------------|----------------|
| PRDs (MD) | `product/` | Markdown + Frontmatter |
| Specs (YAML) | `implementation/` | Tree View / Form View |
| Specs (MD) | `product/` | Markdown |
| Issues (MD) | `issues/` | Markdown + State Transitions |

------

## 4. User Interaction

- **Navigation**: Sidebar tree view for all artifacts.
- **Editing**: (Future) Inline markdown editing or "Open in Cursor" button.
- **Filtering**: Quick filters for "Active Issues", "Pending PRDs", etc.

------

## 5. Success Criteria

- Seamless rendering of complex Mermaid diagrams.
- Fast switching between different document types.
- Clear visualization of the link between a PRD and its implementation spec.

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-38
title: Vibe Document and Issue Explorer
type: FEATURE
status: in_progress
group: null
depends_on:
- PRD-37
created_at: 2026-01-13
updated_at: '2026-01-14T19:42:18.087798'
owner: Core Platform
implementation_id: v01-470
implementation_yaml: v01-470_38_vibe_document_and_issue_explorer.yaml
discussion_id: null
last_synced_at: null
sync_hash: null
issue_number: null
impl_code_ready: false
impl_tests_passed: false
impl_review_passed: false
```
</details>

<!-- vibe-id: PRD-38 -->
