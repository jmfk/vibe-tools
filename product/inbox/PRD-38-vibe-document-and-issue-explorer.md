---
id: PRD-38
title: Vibe Document and Issue Explorer
status: inbox
owner: Core Platform
created_at: 2026-01-13
updated_at: 2026-01-13
---

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
