# Architect Interactive Shell

## Overview
- **Problem statement**: Developers need an interactive way to refine architecture and infrastructure specifications with AI assistance. The process requires persistent sessions, context management, and the ability to switch between advisory (ASK) and agent-authorized (AGENT) modes.
- **User benefits**: Interactive refinement of architecture specs, persistent session state, context file management, editor integration, and clear mode distinction between advisory and automated updates.
- **Success criteria**: Shell provides smooth interactive experience, persists sessions correctly, manages context files, supports both ASK and AGENT modes, and successfully updates architecture/infrastructure specs.

## Feature Inspiration
The `vibe architect` command provides an interactive shell for managing architecture and infrastructure specifications. Users can have conversations with an AI agent to refine their `architecture.md` and `infrastructure.md` files. The shell supports two modes: ASK (advisory, no file changes) and AGENT (authorized to propose updates). Sessions persist between invocations, allowing users to continue conversations.

**Key capabilities**:
- Interactive shell with readline support (tab completion, history)
- Two interaction modes: ASK (default) and AGENT
- Session persistence (history, pending prompts, attached files, mode)
- Context file management (attach additional files to agent context)
- Session memory (persistent instructions sent with every prompt)
- Editor integration (configure external editors for markdown/code)
- Slash commands for navigation and control

## Frontend
N/A - CLI interactive shell interface.

## Backend
- **Interactive Loop**: Main loop reads user input, handles slash commands, accumulates multi-line prompts, displays prompt summaries.
- **Slash Commands**:
  - `/send`, `/s`: Dispatch pending prompt to agent
  - `/reset`, `/r`: Clear session memory and pending prompt
  - `/add`, `/a <text>`: Add persistent instructions to session memory
  - `/mode`, `/m [ASK|AGENT]`: Switch between interaction modes
  - `/files`, `/f [list|add <path>|remove <path>]`: Manage context files
  - `/list memory`, `/l`: View pending prompt, session memory, history
  - `/conf [md|code] <cmd>`: Configure external editors
  - `/show [arch|infra]`: Display current architecture/infrastructure specs
  - `/edit [arch|infra]`: Open spec file in configured editor
  - `/history [list|view <idx>|remove <idx>]`: Manage conversation history
  - `/ps`: Show running agent processes
  - `/kill [all]`: Kill agent processes
  - `/help`, `/h`: Show help
  - `/exit`, `/q`: Exit shell
- **Session Persistence**: Saves to `project/architect-session.json`:
  - History (conversation log)
  - Pending prompt (multi-line input being built)
  - Session memory (persistent instructions)
  - Additional files (attached context files)
  - Mode (ASK/AGENT)
- **Agent Integration**: Uses `run_agent()` to dispatch prompts, includes architecture/infrastructure specs in context, appends session memory, includes attached files.
- **Readline Support**: Tab completion for commands, command history (persisted to `.architect_history`), multi-line input support.
- **Editor Integration**: Configurable external editors for markdown (specs) and code (response files).

## Infrastructure
- **Session Storage**: JSON file in `project/architect-session.json`.
- **History Storage**: Readline history in `project/.architect_history`.
- **Config Storage**: Editor preferences in `project/architect-config.json`.
- **Spec Files**: Reads/writes `specs/architecture.md` and `specs/infrastructure.md`.

## Architecture and Constraints
- **Mode Safety**: ASK mode prevents accidental file modifications, AGENT mode requires explicit authorization.
- **Session Continuity**: Sessions persist across invocations, allowing long-running refinement sessions.
- **Context Management**: Attached files included in every agent prompt, allowing deep context.
- **Readline Compatibility**: Works with both GNU readline and macOS libedit.
- **Error Handling**: Graceful handling of missing files, invalid commands, agent failures.

## Success Criteria
- Interactive shell provides smooth user experience
- Sessions persist correctly between invocations
- Both ASK and AGENT modes work as expected
- Context files properly attached to agent prompts
- Spec files updated correctly in AGENT mode
- Editor integration works for configured editors
- Command completion and history function properly

## Acceptance Tests
1. **Shell Startup**: Run `vibe architect`, verify shell starts, shows help
2. **Prompt Building**: Type multi-line prompt, verify accumulated correctly, summary shown
3. **Send Command**: Build prompt, type `/s`, verify agent called, response displayed
4. **Session Persistence**: Build prompt, exit, restart, verify prompt still there
5. **Mode Switching**: Switch to AGENT mode, verify mode indicator changes
6. **File Attachment**: Use `/f add <file>`, verify file included in agent context
7. **History Management**: Send multiple prompts, use `/history list`, verify history shown
8. **Editor Integration**: Configure editor, use `/edit arch`, verify editor opens
9. **ASK Mode**: In ASK mode, verify no file changes made
10. **AGENT Mode**: In AGENT mode, verify spec files can be updated
