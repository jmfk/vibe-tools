---
discussion_id: D_kwDOQzI0Lc4Ajltf
discussion_url: https://github.com/jmfk/vibe-tools/discussions/42
last_synced_at: '2026-01-10T15:24:44.506426'
sync_hash: 5a80ae050378fc6f75991fd102405041bed9ab57ebde47ae18e1435aeb53934f
---

# PM Interactive Shell

## Overview
- **Problem statement**: Product managers need an interactive way to create and refine PRDs and specifications with AI assistance. The process requires PRD focus (working on specific PRDs), spec management, and integration with the implementation workflow.
- **User benefits**: Interactive PRD creation and refinement, PRD-focused workflows, spec file management, implementation status tracking, and seamless integration with the development workflow.
- **Success criteria**: Shell provides smooth interactive experience, manages PRDs effectively, supports focused workflows, tracks implementation status, and successfully creates/updates spec files.

## Feature Inspiration
The `vibe pm` command provides an interactive shell for managing PRDs and specifications. Users can create new PRDs, refine existing ones, focus on specific PRDs, and track implementation status. The shell is similar to `vibe architect` but focused on PRD/spec management rather than architecture.

**Key capabilities**:
- Interactive shell with readline support
- PRD focus mode (work on specific PRD)
- Spec file management (create, list, delete)
- Implementation status tracking
- Session persistence
- Context file management
- Editor integration
- Slash commands for PRD operations

## Frontend
N/A - CLI interactive shell interface.

## Backend
- **Interactive Loop**: Main loop similar to architect shell, with PRD-focused features.
- **PRD Focus**: `/focus <prd_id>` or `/switch <prd_id>` sets focused PRD, displayed in prompt, included in agent context.
- **Spec Management**:
  - `/list specs` or `/ls specs`: List all spec files in `specs/`
  - `/create <name>`: Create new spec file
  - `/delete <name>`: Delete spec file
  - `/show specs`: Display list of specs
- **Slash Commands** (similar to architect, plus PRD-specific):
  - `/send`, `/s`: Dispatch prompt (includes focused PRD context if set)
  - `/reset`, `/r`: Clear session
  - `/add`, `/a <text>`: Add session memory
  - `/mode`, `/m [ASK|AGENT]`: Switch modes
  - `/files`, `/f [list|add|remove]`: Manage context files
  - `/focus`, `/switch <prd_id>`: Focus on specific PRD
  - `/implemented`, `/i`: Show implementation status
  - `/create <name>`: Create new spec
  - `/delete <name>`: Delete spec
  - `/list`, `/ls [memory|specs]`: List memory or specs
  - `/show specs`: Show spec list
  - `/history`, `/ps`, `/kill`, `/help`, `/exit`: Standard commands
- **Session Persistence**: Saves to `implementation/pm-session.json`:
  - History, pending prompt, session memory, additional files, mode (like architect)
  - `focused_prd`: Currently focused PRD ID
- **Agent Integration**: Includes focused PRD context, spec files, session memory, attached files in agent prompts.
- **Implementation Tracking**: `/implemented` command shows which PRDs are implemented, links to implementation status.

## Infrastructure
- **Session Storage**: JSON file in `implementation/pm-session.json`.
- **History Storage**: Readline history in `implementation/.pm_history`.
- **Config Storage**: Editor preferences in `implementation/pm-config.json`.
- **Spec Files**: Manages files in `specs/` directory.

## Architecture and Constraints
- **PRD Focus**: Focused PRD context automatically included in agent prompts, allowing focused refinement.
- **Spec Management**: Specs stored as markdown files, can be normalized to YAML PRDs later.
- **Integration**: Works with `vibe normalize` (convert specs to PRDs) and `vibe implement` (implement PRDs).
- **Readline Compatibility**: Same readline support as architect shell.
- **Error Handling**: Graceful handling of missing PRDs, invalid spec names, file errors.

## Success Criteria
- Interactive shell provides smooth user experience
- PRD focus mode works correctly
- Spec management (create, list, delete) functions properly
- Sessions persist correctly
- Implementation status tracking works
- Agent prompts include correct context (focused PRD, specs, files)
- Editor integration works

## Acceptance Tests
1. **Shell Startup**: Run `vibe pm`, verify shell starts
2. **PRD Focus**: Use `/focus prd_01`, verify focus shown in prompt
3. **Spec Creation**: Use `/create my_feature`, verify spec file created in `specs/`
4. **Spec Listing**: Use `/ls specs`, verify all specs listed
5. **Prompt with Focus**: Focus on PRD, build prompt, verify PRD context included
6. **Implementation Status**: Use `/implemented`, verify status shown
7. **Session Persistence**: Build prompt, exit, restart, verify state restored
8. **Spec Deletion**: Use `/delete <name>`, verify spec deleted
9. **Agent Context**: Send prompt with focused PRD and attached files, verify all included
10. **Spec Management**: Create, list, and delete multiple specs, verify operations work