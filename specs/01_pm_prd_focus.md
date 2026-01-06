# PRD: PM Focus Mode

## 1. Overview
The current `vibe pm` command loads all PRDs into the AI context simultaneously. This can lead to context overflow and diluted focus when working on a specific feature. This PRD proposes a "Focus Mode" for `vibe pm`, where the tool targets a specific PRD, improves the prompt visibility, and provides dedicated commands for PRD lifecycle management.

## 2. User Experience (UX)

### 2.1 Focus-Aware Prompt
The command-line prompt should clearly indicate which PRD is currently in focus.

- **No Focus**: `(ASK) 👤 ` (Current behavior)
- **With Focus**: `(ASK) [01_auth.md] 👤 `

### 2.2 PRD Lifecycle Commands
New slash commands will be added to `vibe pm` to manage the focused PRD and the `specs/` directory:

- `/list`: List all available PRDs in `specs/` (aliased to `/ls`).
- `/focus <name>`: Set the focus to a specific PRD (aliased to `/f` or `/switch`). If no name is provided, it clears the focus.
- `/create <name>`: Create a new PRD file in `specs/` with a basic template.
- `/delete <name>`: Delete a PRD file from `specs/` after confirmation.

## 3. Functional Requirements

### 3.1 Context Management
- When a PRD is in focus, its full content is explicitly marked as the primary target in the AI prompt.
- Other PRDs should be summarized or excluded from the primary context to save tokens and focus the AI, while still providing enough high-level context if needed.
- `FILE_UPDATE` commands from the AI should default to the focused PRD if no filename is explicitly provided, or the AI should be heavily steered to update the focused file.

### 3.2 Command Implementation
- **`/list`**: Should show files in `specs/` and highlight the one currently in focus.
- **`/focus`**: Should support fuzzy matching or index-based selection from the `/list` output.
- **`/create`**: Should automatically append `.md` if missing and ensure the file is created in the `specs/` directory.
- **`/delete`**: Must require a confirmation (Y/N) before removing any file.

## 4. Technical Specifications

### 4.1 State Management
- The `PM_SESSION_FILE` (typically `.vibe/pm_session.json`) must be updated to store the `focused_prd` filename.
- The `InteractivePM` class should be updated to handle this new state.

### 4.2 Prompt Template
- The `pm_prompt.txt` should be updated (or the logic in `_build_prompt` adjusted) to inject a "PRIMARY FOCUS" section when a PRD is selected.

## 5. Acceptance Criteria
- [ ] The `vibe pm` prompt displays the name of the focused PRD.
- [ ] Users can switch focus between different PRDs using `/focus`.
- [ ] Users can create new PRDs using `/create`.
- [ ] Users can delete PRDs using `/delete` with a confirmation step.
- [ ] The AI correctly identifies and prioritizes the focused PRD in its responses.