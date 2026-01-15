# PRD-041: Global Project Management

## Overview
- **Problem statement**: Currently, vibe-tools is directory-centric. Users need a way to manage multiple projects from a central location, especially in the Tauri desktop application, and have the CLI automatically recognize which project it's working on regardless of the current directory (if it's within a project path).
- **User benefits**: Seamless switching between projects, central management of project metadata and secrets, and a unified experience across CLI and Desktop.
- **Success criteria**: 
    - Global project registry in `~/.vibe-tools/projects.json`.
    - CLI auto-detects project context based on current path.
    - Tauri app provides a project manager UI.
    - Support for project-specific secrets stored in `~/.vibe-tools`.

## Feature Inspiration
Similar to IDE project managers (VS Code, Cursor), but tailored for the vibe-tools workflow where a project is a combination of a local folder, a set of PRDs, and associated metadata like GitHub repositories.

## User Interface (Tauri)
- **Project Pulse (Left Pane)**:
    - `Projects` accordion:
        - List of recent projects.
        - "Manage Projects" button opening a full-screen or modal project manager.
- **Project Manager View**:
    - List view of all registered projects with name, path, and last active timestamp.
    - "New Project" button (Initialize a new vibe project).
    - "Import Project" (Select an existing folder or clone from GitHub).
    - Edit project metadata: Name, Description, GitHub URL, custom secrets.

## CLI Behavior
- On startup, `vibe` checks if the current working directory (or any parent) is registered in `~/.vibe-tools/projects.json`.
- If found, it loads that project's configuration and secrets.
- If not found, it defaults to the local directory behavior (backward compatibility).
- New command: `vibe project`
    - `vibe project list`: List all registered projects.
    - `vibe project add [path]`: Add a folder as a project.
    - `vibe project remove [name]`: Remove from registry.

## Backend / Registry
- **Location**: `~/.vibe-tools/projects.json`
- **Schema**:
```json
{
  "projects": [
    {
      "id": "uuid",
      "name": "vibe-tools",
      "path": "/Users/user/code/vibe-tools",
      "description": "Vibe development tools",
      "metadata": {
        "github_url": "https://github.com/jmfk/vibe-tools"
      },
      "secrets": {
        "OPENAI_API_KEY": "...",
        "GOOGLE_API_KEY": "..."
      }
    }
  ],
  "last_active_project_id": "uuid"
}
```

## Implementation Details
- Add `GlobalProjectRegistry` class in `vibe_tools/utils.py`.
- Update `vibe init` to automatically register the project in the global registry.
- Update `vibe_tools/cli.py` to check the global registry during context initialization.

## Acceptance Tests
1. **Registration**: Run `vibe init` in a new folder, verify it appears in `~/.vibe-tools/projects.json`.
2. **Auto-detection**: `cd` into a project subdirectory and run `vibe status`. Verify it correctly identifies the project name.
3. **Manual Add**: Run `vibe project add .` in an existing vibe project and verify registration.
4. **Tauri List**: Open Tauri app, verify project list matches `projects.json`.

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-041
title: Global Project Management
type: FEATURE
status: backlog
group: core
depends_on: []
created_at: '2026-01-15T12:00:00.000000'
updated_at: '2026-01-15T10:40:53.262970'
```
</details>

<!-- vibe-id: PRD-041 -->
