# PRD-044: Tauri Planner Tab

## Overview
- **Problem statement**: Visualizing the project roadmap and PRD dependencies is difficult in a list-based UI. Users need a Kanban-style board for status tracking and a graphical view for understanding complex relationships between features.
- **User benefits**: Clear project overview, intuitive drag-and-drop management, and better architectural understanding through dependency graphs.
- **Success criteria**:
    - Kanban board with columns: `Inbox`, `Backlog`, `Next`, `In Progress`, `Archive`.
    - Dependency graph view using a library like `reactflow` or `mermaid`.
    - Integrated agent log monitor with real-time updates.
    - Drag-and-drop to move PRDs between lifecycle states.

## Board View (Kanban)
- **Columns**:
    - `Inbox`: Newly created PRDs from `product/inbox`.
    - `Backlog`: Validated PRDs awaiting prioritization.
    - `Next`: Selected PRDs for the next development cycle.
    - `In Progress`: PRDs currently being implemented (limited to one or two active items).
    - `Archive`: Completed or cancelled PRDs.
- **Card Content**: PRD ID, Title, Status icons (Spec ready, PRD ready, Implementation status), and owner.
- **Actions**: Drag-and-drop, right-click menu for status changes, click to open in `Create` tab.

## Graph View
- **Nodes**: PRDs colored by status.
- **Edges**: Directional lines representing `depends_on` metadata.
- **Interaction**: Zoom, pan, and click nodes to view details or select for the board view.

## Agent Monitor (Integrated)
- Located at the bottom of the Planner tab (collapsible).
- **Sub-views**:
    - `Mini Log`: Last 5-10 lines of agent output + status bar (Working/Idle).
    - `Full Log`: Dedicated modal or full-screen view for the active stream of JSON logs from the CLI.
- **Real-time Updates**: Updates automatically as the CLI emits JSON objects in server mode.

## Logic & Constraints
- Moving a PRD to `In Progress` should trigger the appropriate `vibe implement` or `vibe setup` command in server mode.
- Only one PRD can be `In Progress` at a time per agent context.
- Dragging from `In Progress` to `Next` cancels the current implementation task via the server mode protocol.

## Implementation Details
- Create `PlannerBoard` and `PlannerGraph` components.
- Integrate `dnd-kit` or `react-beautiful-dnd` for board interactions.
- Use `reactflow` for the dependency graph visualization.
- Implement `AgentLogMonitor` component that subscribes to the CLI server mode stream.

## Acceptance Tests
1. **Board Layout**: Verify all 5 columns are present and display PRD cards correctly.
2. **Drag and Drop**: Move a card from `Inbox` to `Backlog` and verify the file is moved to the corresponding folder in `product/`.
3. **Graph Rendering**: Verify that PRDs with `depends_on` metadata are connected correctly in the graph view.
4. **Log Streaming**: Start an agent task and verify that logs appear in real-time in the `Agent Monitor`.

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-044
title: Tauri Planner Tab
type: FEATURE
status: done
group: tauri
depends_on:
- PRD-042
- PRD-043
created_at: '2026-01-15T12:00:00.000000'
updated_at: '2026-01-17T22:40:12.051582'
impl_code_ready: true
impl_tests_passed: true
impl_review_passed: true
```
</details>

<!-- vibe-id: PRD-044 -->
