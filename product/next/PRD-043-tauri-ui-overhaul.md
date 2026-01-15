# PRD-043: Tauri UI Overhaul

## Overview
- **Problem statement**: The current Tauri app layout is basic and lacks professional-grade features like resizable panes and an optimized workflow. The file explorer is redundant for now, and the navigation needs to focus on high-level project activities.
- **User benefits**: Improved usability, better information density, and a more focused interface for PRD management and agent interaction.
- **Success criteria**:
    - Three-pane layout with resizable borders.
    - AI Pane moved to the right.
    - "Project Pulse" sidebar with accordions.
    - Main tab system: Planner, Create, Issues.
    - File Explorer removed to reduce clutter.

## Layout Specification
- **Left Pane (Project Pulse)**: Fixed-width (resizable), containing accordions for:
    - `Projects`: Current project info and switcher.
    - `Vibe Explorer (PRDs)`: Hierarchical view of PRDs (Inbox, Next, In Progress, etc.).
    - `Properties`: Context-aware properties of the selected item.
- **Center Pane (Main Content)**: Flexible-width, containing a Tab system:
    - `Planner`: Board and Graph views for project planning.
    - `Create`: Interactive PRD writer.
    - `Issues`: Local and GitHub issue management.
- **Right Pane (AI / Interaction)**: Resizable, containing:
    - Agent chat interface.
    - Real-time command output.
    - Performance/Cost metrics.

## UI Components
- **Resizable Panes**: Use a library like `react-resizable-panels` or custom CSS grid with drag handles.
- **Accordions**: Clean, modern accordion components for the sidebar.
- **Tabs**: Top-level navigation tabs for switching main views.
- **Global Header**: Project name, global status (Idle/Working), and settings icon.

## Logic & Navigation
- Selecting a PRD in the "Vibe Explorer" sidebar automatically switches the main tab to `Create` or `Planner` and loads that PRD's context.
- The "AI Pane" remains persistent across tab switches to allow for continuous interaction.
- Project switching via the `Projects` accordion updates the entire app state and working directory.

## Implementation Details
- Refactor `frontend/src/App.tsx` to use the new layout structure.
- Remove `FileExplorer` component and its associated logic.
- Implement `ResizablePane` component with persistence (remembering user's preferred widths).
- Add `ProjectPulse` component for the left sidebar.
- Move existing AI interaction logic to the new right pane location.

## Acceptance Tests
1. **Resizing**: Verify all three panes can be resized by dragging their borders.
2. **Persistence**: Resize a pane, refresh the app, and verify the width is preserved.
3. **Accordions**: Verify all sidebar accordions can be expanded and collapsed.
4. **Tab Switching**: Verify switching between Planner, Create, and Issues tabs works correctly without losing AI pane context.
5. **Layout Balance**: Verify the AI pane is on the right side and the Project Pulse is on the left.

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-043
title: Tauri UI Overhaul
type: FEATURE
status: planned
group: tauri
depends_on:
- PRD-041
- PRD-042
created_at: '2026-01-15T12:00:00.000000'
updated_at: '2026-01-15T10:40:17.185067'
```
</details>

<!-- vibe-id: PRD-043 -->
