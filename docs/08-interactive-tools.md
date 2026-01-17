# Interactive Tools

## Overview

vibe-tools provides two powerful interactive shells for managing project specifications:

- **`vibe architect`**: Architecture & Infrastructure manager
- **`vibe pm`**: PRD & Specification manager

Both tools provide persistent sessions, context management, and AI-assisted refinement of specifications.

## vibe architect

Interactive shell for managing architecture and infrastructure specifications.

### Purpose

- Refine system architecture
- Manage infrastructure specifications
- AI-assisted design decisions
- Persistent session management

### Starting Architect

```bash
vibe architect
# Or with initial query:
vibe architect "Review the current architecture"
```

### Modes

**ASK Mode (Default)**
- Agent provides analysis and guidance
- Does not modify files
- Safe for exploration

**AGENT Mode**
- Agent is authorized to modify files
- Updates `product/SRD-architecture.md` and `product/SRD-infrastructure.md`
- Use with caution

**Switching Modes:**
```
/mode ASK
/mode AGENT
/ask      # Shortcut to ASK mode
/agent    # Shortcut to AGENT mode
```

### Slash Commands

#### Prompt Management

**`/send`, `/s`**
- Dispatch current pending prompt to Architect
- Sends prompt with context files and session memory

**`/reset`, `/r`**
- Clear current session memory and pending prompt
- Starts fresh

**`/add`, `/a <text>`**
- Add persistent instructions to session memory
- Sent with every prompt
- Example: `/add Always use microservices architecture`

#### Context Management

**`/files`, `/f [list|add <path>|remove <path>]`**
- Manage additional files included in prompt context
- Example:
  ```
  /files add src/main.py
  /files list
  /files remove src/main.py
  ```

**`/show [arch|infra]`**
- Display current architecture or infrastructure spec
- Example: `/show arch`

**`/edit [path]`**
- Open file in configured editor
- Requires editor configuration: `/conf code vim`

#### History Management

**`/history [list|view <idx>|remove <idx>]`**
- View interaction history
- Example:
  ```
  /history list
  /history view 0
  /history remove 0
  ```

#### Session Management

**`/list memory`, `/l`**
- View pending prompt, session memory, and history summary

**`/ps`**
- List active agent processes

**`/kill [all]`**
- Kill active agent processes

**`/conf [md|code] <cmd>`**
- Configure external editors
- Example: `/conf md typora`

**`/help`, `/h`**
- Show available commands

**`/c`**
- Clear terminal prompt history

**`/exit`, `/q`**
- Exit the session

### Session Persistence

Sessions are saved in `implementation/architect-session.json`:
- Pending prompts
- Session memory
- History
- Attached files
- Mode preference

Sessions persist between invocations.

### Example Workflow

```
$ vibe architect

(ASK) 👤 Review the current architecture and suggest improvements

📝 Pending Prompt (1 lines):
  Review the current architecture and suggest improvements
Type /s to send, /r to reset, or keep typing to add more.

(ASK) 👤 /s

[Agent responds with analysis...]

(ASK) 👤 /add Focus on scalability

✅ Session Memory Updated (1 lines):
  Focus on scalability

(ASK) 👤 /mode AGENT

✅ Switched to AGENT mode.

(AGENT) 👤 Update the architecture to use microservices

📝 Pending Prompt (1 lines):
  Update the architecture to use microservices
Type /s to send, /r to reset, or keep typing to add more.

(AGENT) 👤 /s

[Agent updates SRD-architecture.md...]
```

## vibe pm

Interactive shell for managing PRDs and product specifications.

### Purpose

- Create and refine PRDs
- Manage product specifications
- AI-assisted requirement gathering
- PRD lifecycle management

### Starting PM

```bash
vibe pm
# Or with initial query:
vibe pm "Create a PRD for user authentication"
```

### Features

Similar to `vibe architect` but focused on PRDs:
- Same slash commands (with PRD-specific additions)
- Session persistence in `implementation/pm-session.json`
- Focus mode for working on specific PRDs

### PRD-Specific Commands

**`/focus <prd_id>`, `/f <prd_id>`**
- Focus on a specific PRD
- All operations apply to focused PRD
- Example: `/focus prd_01_auth`

**`/switch <prd_id>`**
- Switch focus to different PRD

**`/create <name>`**
- Create a new PRD
- Opens in editor or creates via agent

**`/delete <prd_id>`**
- Delete a PRD (with confirmation)

**`/implemented`, `/i`**
- Mark focused PRD as implemented
- Updates project state

**`/show specs`**
- List all PRDs in specs directory

**`/list specs`**
- Show all available PRDs

### Slash Commands

All commands from `vibe architect` plus PRD-specific ones:

- `/send`, `/s` - Dispatch prompt
- `/reset`, `/r` - Clear session
- `/add`, `/a` - Add to session memory
- `/mode`, `/m` - Switch modes
- `/files` - Manage context files
- `/history` - View history
- `/focus`, `/f` - Focus on PRD
- `/implemented`, `/i` - Mark as implemented
- `/show specs` - List PRDs
- `/list specs` - Show PRDs
- `/ps` - List processes
- `/kill` - Kill processes
- `/conf` - Configure editors
- `/help` - Show help
- `/exit`, `/q` - Exit

### Session Persistence

Sessions saved in `implementation/pm-session.json`:
- Pending prompts
- Session memory
- History
- Focused PRD
- Attached files

### Example Workflow

```
$ vibe pm

(ASK) 👤 Create a PRD for user authentication

📝 Pending Prompt (1 lines):
  Create a PRD for user authentication
Type /s to send, /r to reset, or keep typing to add more.

(ASK) 👤 /s

[Agent creates PRD...]

(ASK) 👤 /focus prd_01_auth

✅ Focused on: prd_01_auth

(ASK) 👤 Add OAuth2 support

📝 Pending Prompt (1 lines):
  Add OAuth2 support
Type /s to send, /r to reset, or keep typing to add more.

(ASK) 👤 /s

[Agent updates PRD...]

(ASK) 👤 /mode AGENT

✅ Switched to AGENT mode.

(AGENT) 👤 /s

[Agent updates product/01_auth.md...]
```

## Common Features

### Tab Completion

Both tools support tab completion for:
- Slash commands
- Subcommands
- File paths (when applicable)

### History

- Persistent command history
- Saved between sessions
- Accessible via readline (up/down arrows)

### Editor Integration

Configure editors for different file types:

```
/conf md typora          # Markdown editor
/conf code code          # Code editor (VS Code)
/conf code vim           # Vim for code
```

### Context Files

Attach files to provide additional context:

```
/files add src/models.py
/files add tests/test_models.py
/files list
```

These files are included in every agent prompt.

### Session Memory

Add persistent instructions:

```
/add Always use type hints
/add Follow PEP 8 style guide
/list memory
```

Session memory is sent with every prompt.

## Best Practices

### Using Architect

1. **Start in ASK mode**: Explore before making changes
2. **Use session memory**: Add design principles once
3. **Attach relevant files**: Provide code context
4. **Review before AGENT mode**: Understand changes first
5. **Save frequently**: Sessions auto-save, but commit important changes

### Using PM

1. **Focus on one PRD**: Use `/focus` for clarity
2. **Iterate on PRDs**: Refine through multiple interactions
3. **Link dependencies**: Reference other PRDs
4. **Normalize regularly**: Convert to YAML after changes
5. **Track implementation**: Use `/implemented` when done

### General Tips

1. **Use shortcuts**: `/s`, `/r`, `/q` for common operations
2. **Check history**: Review past interactions
3. **Monitor processes**: Use `/ps` to see active agents
4. **Configure editors**: Set up for efficient editing
5. **Save context**: Attach relevant files early

## Troubleshooting

### Session Not Loading

- Check `implementation/architect-session.json` or `implementation/pm-session.json`
- Verify file permissions
- Try `/reset` to start fresh

### Editor Not Opening

- Configure editor: `/conf code <command>`
- Verify editor command works in terminal
- Check file path exists

### Agent Not Responding

- Check `/ps` for active processes
- Use `/kill all` if needed
- Verify agent configuration: `vibe status`

### Files Not Attaching

- Verify file paths are correct
- Use absolute paths if relative don't work
- Check file permissions

See [Troubleshooting](12-troubleshooting.md) for more help.

---

<details>
<summary>Metadata</summary>

```yaml
id: DOC-008
title: Interactive Tools
type: DOCUMENTATION
status: active
```

</details>

<!-- vibe-id: DOC-008 -->
