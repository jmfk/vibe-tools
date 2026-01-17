import atexit
import json
import logging
import os
import signal
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from .utils import (
    VIBE_PROJECT_DIR,
    ensure_dir,
    is_test_mode,
    load_config,
    log_large_output,
    run_command,
    out_print,
    out_debug,
)

logger = logging.getLogger("vibe_tools")

ACTIVE_AGENTS_FILE = VIBE_PROJECT_DIR / "active_agents.json"


class AgentManager:
    """Manages AI agent processes, tracking PIDs and ensuring clean termination."""

    def __init__(self):
        self.active_agents_file = ACTIVE_AGENTS_FILE
        self.session_pids = set()
        ensure_dir(VIBE_PROJECT_DIR)

    def _load_active_agents(self) -> Dict[str, Any]:
        if self.active_agents_file.exists():
            try:
                return json.loads(self.active_agents_file.read_text())
            except Exception:
                return {}
        return {}

    def _save_active_agents(self, agents: Dict[str, Any]):
        self.active_agents_file.write_text(json.dumps(agents, indent=2))

    def register_agent(
        self, pid: int, command: List[str], chat_id: Optional[str] = None
    ):
        """Registers a new agent process."""
        self.session_pids.add(pid)
        agents = self._load_active_agents()
        agents[str(pid)] = {
            "pid": pid,
            "command": " ".join(command),
            "chat_id": chat_id,
            "start_time": time.time(),
        }
        self._save_active_agents(agents)

    def unregister_agent(self, pid: int):
        """Unregisters an agent process."""
        if pid in self.session_pids:
            self.session_pids.remove(pid)
        agents = self._load_active_agents()
        if str(pid) in agents:
            del agents[str(pid)]
            self._save_active_agents(agents)

    def get_active_agents(self) -> List[Dict[str, Any]]:
        """Returns a list of all tracked active agent processes."""
        agents = self._load_active_agents()
        active = []
        for pid_str, info in agents.items():
            pid = int(pid_str)
            if self._is_process_running(pid):
                active.append(info)
            else:
                # Cleanup stale tracking
                agents = self._load_active_agents()
                if pid_str in agents:
                    del agents[pid_str]
                    self._save_active_agents(agents)
        return active

    def _is_process_running(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def cleanup_process_group(self, pid: int):
        """Kills an entire process group."""
        try:
            # Try to kill the whole process group
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
            time.sleep(1)
            if self._is_process_running(pid):
                os.killpg(pgid, signal.SIGKILL)
        except Exception as e:
            logger.debug(f"Error cleaning up process group for PID {pid}: {e}")
            # Fallback to killing just the process
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass

    def cleanup_session(self):
        """Kills all agent processes started in this session."""
        for pid in list(self.session_pids):
            self.cleanup_process_group(pid)
            self.unregister_agent(pid)

    def cleanup_all(self) -> List[str]:
        """Kills all tracked agent processes and their child processes."""
        agents = self._load_active_agents()
        killed = []
        for pid_str in list(agents.keys()):
            pid = int(pid_str)
            info = agents[pid_str]
            self.cleanup_process_group(pid)
            killed.append(f"{pid} ({info['command'][:50]}...)")
            self.unregister_agent(pid)
        return killed


agent_manager = AgentManager()


atexit.register(agent_manager.cleanup_session)


def get_agent_command(
    agent: str, prompt: str, chat_id: Optional[str] = None
) -> List[str]:
    """Constructs the command to invoke the specified AI agent."""
    if agent == "cursor-agent":
        config = load_config()
        agent_config = config.get("cursor-agent", {})
        force = agent_config.get("force", True)

        cmd = ["cursor-agent", "-p"]
        if force:
            cmd.append("--force")

        if chat_id:
            cmd.extend(["--resume", chat_id])

        cmd.extend(
            ["--output-format", "stream-json", "--stream-partial-output", prompt]
        )
        return cmd
    elif agent == "claude":
        return ["claude", "-p", prompt]
    elif agent == "antigravity":
        return ["antigravity", "-p", prompt]
    return ["echo", "UNKNOWN_AGENT", prompt]


def run_agent(
    command: List[str], stream: bool = False
) -> Tuple[str, int, Optional[str]]:
    """Runs an agent command, optionally preventing sleep and streaming output."""
    if os.environ.get("VIBE_AGENT_ACTIVE") == "1" or is_test_mode():
        logger.warning(
            "Recursive or test-mode agent call detected. Preventing execution."
        )
        return "ERROR: Agent call blocked in current environment.", 1, None

    is_cursor_agent = command[0] == "cursor-agent" or (
        len(command) > 2 and command[2] == "cursor-agent"
    )

    # Use os.setsid to create a new process group for robust cleanup
    env = os.environ.copy()
    env["VIBE_AGENT_ACTIVE"] = "1"

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        preexec_fn=os.setsid if sys.platform != "win32" else None,
        env=env,
    )

    agent_manager.register_agent(process.pid, command)

    # Log the agent call details
    out_debug(f"🤖 Starting agent: {command[0]}", source="agent", data={
        "command_line": f"$ {' '.join(command)}",
        "stdio": "", # Agent usually takes parameters via CLI
        "pid": process.pid,
    })

    # Log the prompt if it's large
    prompt_found = False
    for i, arg in enumerate(command):
        if arg == "-p" or arg == "--prompt":
            if i + 1 < len(command):
                log_large_output("agent_prompt", command[i + 1])
                prompt_found = True
                break
    if not prompt_found and command:
        # For cursor-agent, prompt is often the last argument
        log_large_output("agent_prompt", command[-1])

    try:
        accumulated_assistant_text = []
        full_event_log = []
        full_result_text = None
        detected_chat_id = None
        active_tool_calls = {}

        if stream or is_cursor_agent:
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                if is_cursor_agent:
                    try:
                        data = json.loads(line)
                        full_event_log.append(line)
                        event_type = data.get("type")
                        subtype = data.get("subtype")

                        # Capture chat_id if available
                        if not detected_chat_id:
                            detected_chat_id = (
                                data.get("chatId")
                                or data.get("chat_id")
                                or data.get("session_id")
                            )

                        if event_type == "system":
                            model = data.get("model", "unknown")
                            out_print(f"🤖 System: {model}", flush=True, source="agent", data=data)
                            log_large_output("system", json.dumps(data, indent=2))

                        elif event_type == "user":
                            out_print("👤 User!", flush=True, source="agent", data=data)
                            message = data.get("message", {})
                            content_list = message.get("content", [])
                            for content in content_list:
                                if content.get("type") == "text":
                                    text = content.get("text", "")
                            log_large_output("user", json.dumps(content_list, indent=2))

                        elif event_type == "assistant":
                            out_print("🤖 Assistant!", flush=True, source="agent", data=data)
                            message = data.get("message", {})
                            content_list = message.get("content", [])
                            for content in content_list:
                                if content.get("type") == "text":
                                    text = content.get("text", "")
                                    if text:
                                        accumulated_assistant_text.append(text)
                            log_large_output(
                                "assistant", json.dumps(content_list, indent=2)
                            )

                        elif event_type == "tool_call":
                            if subtype == "started":
                                tool_call = data.get("tool_call", {})
                                for tool_name, tool_info in tool_call.items():
                                    call_id = tool_info.get("call_id") or tool_name
                                    active_tool_calls[call_id] = tool_info.get("args", {})
                                if stream:
                                    _print_tool_call_start(tool_call, data)
                            else:
                                tool_call = data.get("tool_call", {})
                                if stream:
                                    _print_tool_call_done(tool_call, data, active_tool_calls)
                                for tool_name, tool_info in tool_call.items():
                                    call_id = tool_info.get("call_id") or tool_name
                                    if call_id in active_tool_calls:
                                        del active_tool_calls[call_id]

                        elif event_type == "thinking":
                            text = data.get("text", None)
                            if stream and text:
                                # Thinking is usually suppressed in print mode but we handle it just in case
                                out_print(f"🤔 {text}", flush=True, source="agent", data=data)

                        elif event_type == "result":
                            full_result_text = data.get("result", "")
                            is_error = data.get("is_error", False)
                            if subtype == "success" and not is_error:
                                if stream:
                                    out_print("\n✅ Done.", flush=True, source="agent", data=data)
                            else:
                                if stream:
                                    out_print(
                                        f"\n❌ Error: {full_result_text}",
                                        flush=True,
                                        source="agent",
                                        data=data,
                                    )

                    except json.JSONDecodeError:
                        if stream:
                            out_print(line, flush=True, source="agent")
                        full_event_log.append(line)
                else:
                    if stream:
                        out_print(line, flush=True, source="agent")
                    full_event_log.append(line)

            process.wait()

            # For cursor-agent, final_output should combine assistant text and any final result text
            if is_cursor_agent:
                assistant_content = "".join(accumulated_assistant_text)
                if full_result_text:
                    if assistant_content:
                        final_output = (
                            assistant_content
                            + "\n\n--- FINAL RESULT ---\n"
                            + full_result_text
                        )
                    else:
                        final_output = full_result_text
                else:
                    final_output = assistant_content

                # Log both the clean output and the full raw event log
                log_large_output("agent_output", final_output)
                log_large_output("agent_raw_events", "\n".join(full_event_log))
            else:
                final_output = "".join(full_event_log)
                log_large_output("agent_output", final_output)

            # Log the final result with command_line/stdio/stdout/stderr
            out_debug(f"Agent {command[0]} finished", source="agent", data={
                "command_line": f"$ {' '.join(command)}",
                "stdio": "", 
                "stdout": final_output,
                "stderr": "\n".join(full_event_log) if is_cursor_agent else "",
                "code": process.returncode
            })

            return final_output, process.returncode, detected_chat_id
        else:
            stdout, stderr = process.communicate()
            log_large_output("agent_output", stdout)

            # Log the final result with command_line/stdio/stdout/stderr
            out_debug(f"Agent {command[0]} finished", source="agent", data={
                "command_line": f"$ {' '.join(command)}",
                "stdio": "",
                "stdout": stdout,
                "stderr": stderr,
                "code": process.returncode
            })

            return stdout, process.returncode, None

    except KeyboardInterrupt:
        logger.info(f"Agent process {process.pid} interrupted.")
        raise
    finally:
        if process.poll() is None:
            agent_manager.cleanup_process_group(process.pid)
        agent_manager.unregister_agent(process.pid)


def _print_tool_call_start(tool_call: Dict[str, Any], data: Dict[str, Any]):
    for key, value in tool_call.items():
        if key in ["readToolCall", "lsToolCall", "globToolCall"]:
            continue
        log_large_output(f"{key}-start", json.dumps(value.get("result", {}), indent=2))
    if "readToolCall" in tool_call:
        pass  # Silenced
    elif "writeToolCall" in tool_call:
        output = tool_call["writeToolCall"]
        path = output["args"].get("path")
        out_print(f"🔧 Writing: {path}", flush=True, source="agent", data=data)
    elif "editToolCall" in tool_call:
        output = tool_call["editToolCall"]
        path = output["args"].get("path")
        out_print(f"🔧 Editing: {path}", flush=True, source="agent", data=data)
    elif "lsToolCall" in tool_call:
        pass  # Silenced
    elif "shellToolCall" in tool_call:
        output = tool_call["shellToolCall"]
        commandText = output["args"].get("command")
        out_print(f"🔧 Command: {commandText}", flush=True, source="agent", data=data)
    elif "globToolCall" in tool_call:
        pass  # Silenced
    elif "function" in tool_call:
        output = tool_call["function"]
        name = output.get("name")
        arguments = output.get("arguments")
        out_print(f"🛠️ Calling: {name} ({arguments})", flush=True, source="agent", data=data)


def _print_tool_call_done(tool_call: Dict[str, Any], data: Dict[str, Any], active_tool_calls: Dict[str, Any] = None):
    for key, value in tool_call.items():
        if key in ["readToolCall", "lsToolCall", "globToolCall"]:
            result = value.get("result", {})
            if result.get("success"):
                continue
        log_large_output(f"{key}-done", json.dumps(value.get("result", {}), indent=2))
    if "readToolCall" in tool_call:
        tool_info = tool_call.get("readToolCall", {})
        result = tool_info.get("result", {})
        success = result.get("success")
        if success:
            pass  # Silenced
        else:
            call_id = tool_info.get("call_id") or "readToolCall"
            args = (active_tool_calls or {}).get(call_id, {})
            path = args.get("path") or "unknown path"
            out_print(f"🚫 Read failed: {path}", flush=True, source="agent", data=data)
    elif "writeToolCall" in tool_call:
        result = tool_call.get("writeToolCall", {}).get("result", {})
        success = result.get("success")
        if success:
            lines = success.get("linesCreated", 0)
            out_print(f"✅ Wrote {lines} lines.", flush=True, source="agent", data=data)
        else:
            out_print("🚫 Write failed.", flush=True, source="agent", data=data)
    elif "editToolCall" in tool_call:
        result = tool_call.get("editToolCall", {}).get("result", {})
        success = result.get("success")
        if success:
            out_print("✅ Edit complete.", flush=True, source="agent", data=data)
        else:
            out_print("🚫 Edit failed.", flush=True, source="agent", data=data)
    elif "lsToolCall" in tool_call:
        tool_info = tool_call.get("lsToolCall", {})
        result = tool_info.get("result", {})
        success = result.get("success")
        if success:
            pass  # Silenced
        else:
            call_id = tool_info.get("call_id") or "lsToolCall"
            args = (active_tool_calls or {}).get(call_id, {})
            path = args.get("path") or "unknown path"
            out_print(f"🚫 List failed: {path}", flush=True, source="agent", data=data)
    elif "shellToolCall" in tool_call:
        result = tool_call.get("shellToolCall", {}).get("result", {})
        success = result.get("success")
        if success:
            ms = success.get("executionTime", 0)
            out_print(f"✅ Command successful ({ms}ms).", flush=True, source="agent", data=data)
        else:
            failure = result.get("failure", {})
            code = failure.get("exitCode", "unknown")
            out_print(
                f"❌ Command failed (Exit code: {code}).", flush=True, source="agent", data=data
            )
    elif "globToolCall" in tool_call:
        tool_info = tool_call.get("globToolCall", {})
        result = tool_info.get("result", {})
        success = result.get("success")
        if success:
            pass  # Silenced
        else:
            call_id = tool_info.get("call_id") or "globToolCall"
            args = (active_tool_calls or {}).get(call_id, {})
            pattern = args.get("globPattern") or "unknown pattern"
            out_print(f"🚫 Search failed: {pattern}", flush=True, source="agent", data=data)
    elif "function" in tool_call:
        result = tool_call.get("function", {}).get("result", {})
        out_print(f"🛠️ Done: {result}", flush=True, source="agent", data=data)


def get_agent_processes() -> List[Dict[str, Any]]:
    """Lists all active agent-related processes (using tracking state and pgrep)."""
    # 1. Start with tracked agents
    active_tracked = agent_manager.get_active_agents()

    # 2. Augmented with pgrep to find floating ones
    stdout_vibe, _ = run_command(["pgrep", "-f", "vibe"], check=False)
    stdout_agent, _ = run_command(["pgrep", "-f", "cursor-agent"], check=False)

    pids = set()
    if stdout_vibe.strip():
        pids.update(stdout_vibe.strip().splitlines())
    if stdout_agent.strip():
        pids.update(stdout_agent.strip().splitlines())

    tracked_pids = {str(a["pid"]) for a in active_tracked}
    my_pid = str(os.getpid())

    all_processes = []
    for a in active_tracked:
        a["tracked"] = True
        all_processes.append(a)

    for pid in pids:
        if pid == my_pid or pid in tracked_pids:
            continue

        info_out, _ = run_command(["ps", "-p", pid, "-o", "args="], check=False)
        cmd_line = info_out.strip()

        if "vibe" in cmd_line or "agent" in cmd_line:
            all_processes.append(
                {
                    "pid": int(pid),
                    "command": cmd_line,
                    "target": "unknown",
                    "tracked": False,
                }
            )
    return all_processes


def cleanup_stale_processes() -> List[str]:
    """Kills tracked and floating agent processes."""
    killed = agent_manager.cleanup_all()

    floating = get_agent_processes()
    for p in floating:
        if p.get("tracked") is False:
            pid = p["pid"]
            try:
                os.kill(pid, signal.SIGTERM)
                killed.append(f"{pid} ({p['command'][:50]}...) [floating]")
            except Exception:
                pass

    return killed
