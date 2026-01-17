# PRD-042: CLI Server Mode & Integration

## Overview
- **Problem statement**: The Tauri desktop app needs a robust way to interact with the Python CLI, especially for long-running agent tasks and interactive commands. Simple shell execution is insufficient for streaming updates and handling complex input/output.
- **User benefits**: Real-time feedback in the desktop app, ability to manage long-running tasks, and a consistent bridge between the CLI and the GUI.
- **Success criteria**:
    - Global `--server` flag for all `vibe` commands.
    - JSON-based protocol for communication over standard streams.
    - Non-blocking interaction: GUI can send additional instructions to a running command.
    - Real-time streaming of agent logs and status updates to the GUI.

## Feature Inspiration
Similar to Language Server Protocol (LSP) or how Docker/Kubernetes CLIs handle streaming output. The goal is to make the CLI a "backend" for the Tauri "frontend".

## Protocol Specification
When started with `--server`, the CLI expects and produces JSON objects:

### Input (STDIN)
- **Initial Payload**: The command arguments and options wrapped in a JSON object.
- **Runtime Commands**: For long-running agents, the GUI can send:
    - `{"type": "cancel"}`: Gracefully stop the current agent.
    - `{"type": "input", "value": "..."}`: Provide input to an interactive prompt.

### Output (STDOUT)
- **Status Updates**: `{"type": "status", "phase": "implement", "status": "in_progress", "progress": 45}`
- **Logs**: `{"type": "log", "level": "info", "source": "agent", "message": "..."}`
- **Final Result**: `{"type": "result", "code": 0, "data": { ... }}`

### Errors (STDERR)
- **Error Objects**: `{"type": "error", "message": "...", "traceback": "..."}`

## Implementation Details
- **CLI Bridge**: Update `vibe_tools/cli.py` to check for `sys.argv` containing `--server`.
- **Output Redirection**: In server mode, replace standard `print` and `logger` calls with a JSON formatter that writes to STDOUT.
- **Input Loop**: For long-running commands, start a background thread to listen for JSON objects on STDIN and route them to the active agent or process.
- **Interactive Commands**: Modify `click.prompt` and similar interactive calls to emit a `{"type": "prompt", "message": "..."}` object and wait for a response on STDIN when in server mode.

## Tauri Integration
- Use Tauri's `Command` API to spawn the Python process.
- Implement a listener for the process's `stdout` and `stderr`.
- Parse incoming JSON and update the frontend state in real-time.
- Handle process termination by reading the final `result` object.

## Acceptance Tests
1. **Basic Command**: Run `vibe status --server`. Verify it returns a single JSON object with the status report data.
2. **Streaming**: Run `vibe implement --server`. Verify it emits multiple log and status objects as the agent works.
3. **Cancellation**: Start `vibe implement --server`, send `{"type": "cancel"}` via STDIN, and verify the command exits gracefully with a "cancelled" status.
4. **Interactive Prompt**: Run a command that requires input (e.g., `vibe init --server`), verify it emits a `prompt` object and correctly processes the JSON response sent to STDIN.

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-042
title: CLI Server Mode & Integration
type: FEATURE
status: done
group: core
depends_on:
- PRD-041
created_at: '2026-01-15T12:00:00.000000'
updated_at: '2026-01-17T22:40:12.043053'
impl_code_ready: true
impl_tests_passed: true
impl_review_passed: true
```
</details>

<!-- vibe-id: PRD-042 -->
