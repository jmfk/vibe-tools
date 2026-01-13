import json
import logging
import os
import pathlib
import signal
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from .utils import (
    CONFIG_FILE,
    LOGS_DIR,
    VIBE_PROJECT_DIR,
    ensure_dir,
    load_config,
    run_command,
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

    def register_agent(self, pid: int, command: List[str], chat_id: Optional[str] = None):
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
import atexit

atexit.register(agent_manager.cleanup_session)


def get_agent_command(
    agent: str, prompt: str, chat_id: Optional[str] = None
) -> List[str]:
    """Constructs the command to invoke the specified AI agent."""
    if agent == "cursor-agent":
        config = load_config()
        agent_config = config.get("agent", {})
        force = agent_config.get("force", True)

        cmd = ["agent", "-p"]
        if force:
            cmd.append("--force")

        if chat_id:
            cmd.extend(["--resume", chat_id])

        cmd.extend(["--output-format", "stream-json", "--stream-partial-output", prompt])
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
    is_cursor_agent = command[0] == "agent" or (
        len(command) > 2 and command[2] == "agent"
    )
    
    # Use os.setsid to create a new process group for robust cleanup
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        preexec_fn=os.setsid if sys.platform != "win32" else None,
    )

    agent_manager.register_agent(process.pid, command)

    try:
        output = []
        accumulated_assistant_text = []
        detected_chat_id = None

        if stream or is_cursor_agent:
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                if is_cursor_agent:
                    try:
                        data = json.loads(line)
                        event_type = data.get("type")
                        subtype = data.get("subtype")

                        # Capture chat_id if available in any event
                        if not detected_chat_id:
                            detected_chat_id = data.get("chatId") or data.get("chat_id")

                        if event_type == "assistant":
                            message = data.get("message", {})
                            content_list = message.get("content", [])
                            for content in content_list:
                                if content.get("type") == "text":
                                    text = content.get("text", "")
                                    if text:
                                        if stream:
                                            print(f"💬 {text}", flush=True)
                                        accumulated_assistant_text.append(text)

                        elif event_type == "tool_call":
                            if subtype == "started":
                                tool_call = data.get("tool_call", {})
                                if stream:
                                    _print_tool_call_start(tool_call, data)
                            else:
                                tool_call = data.get("tool_call", {})
                                if stream:
                                    _print_tool_call_done(tool_call, data)

                        elif event_type == "thinking":
                            text = data.get("text", None)
                            if stream:
                                if text:
                                    print(f"🤔 Thinking:\n{text}", flush=True)
                                else:
                                    print("...", flush=True)

                        elif event_type == "result":
                            if subtype == "success":
                                full_result = data.get("result", "")
                                output = [full_result]

                    except json.JSONDecodeError:
                        if stream:
                            print(line, flush=True)
                        output.append(line + "\n")
                else:
                    if stream:
                        print(line, flush=True)
                    output.append(line + "\n")

            process.wait()
            final_output = (
                "".join(output)
                if not is_cursor_agent
                else (output[0] if output else "".join(accumulated_assistant_text))
            )
            return final_output, process.returncode, detected_chat_id
        else:
            stdout, stderr = process.communicate()
            return stdout, process.returncode, None

    except KeyboardInterrupt:
        logger.info(f"Agent process {process.pid} interrupted.")
        raise
    finally:
        if process.poll() is None:
            agent_manager.cleanup_process_group(process.pid)
        agent_manager.unregister_agent(process.pid)


def _print_tool_call_start(tool_call: Dict[str, Any], data: Dict[str, Any]):
    if "readToolCall" in tool_call:
        path = tool_call["readToolCall"]["args"].get("path")
        print(f"📖 Reading: {path}", flush=True)
    elif "writeToolCall" in tool_call:
        path = tool_call["writeToolCall"]["args"].get("path")
        print(f"🔧 Writing: {path}", flush=True)
    elif "editToolCall" in tool_call:
        path = tool_call["editToolCall"]["args"].get("path")
        print(f"🔧 Editing: {path}", flush=True)
    elif "lsToolCall" in tool_call:
        path = tool_call["lsToolCall"]["args"].get("path")
        print(f"🔧 List Directory: {path}", flush=True)
    elif "shellToolCall" in tool_call:
        commandText = tool_call["shellToolCall"]["args"].get("command")
        print(f"🔧 Command: {commandText}", flush=True)
    elif "globToolCall" in tool_call:
        globPattern = tool_call["globToolCall"]["args"].get("globPattern")
        print(f"🔧 globToolCall: {globPattern}", flush=True)
    elif "function" in tool_call:
        name = tool_call["function"].get("name")
        arguments = tool_call["function"].get("arguments")
        print(f"🛠️ Calling tool: {name} ({arguments})", flush=True)


def _print_tool_call_done(tool_call: Dict[str, Any], data: Dict[str, Any]):
    result = tool_call.get("result", {})
    if "readToolCall" in tool_call:
        success = result.get("success", None)
        if success:
            message = success.get("message", "")
            print(f"📖 Reading Done: {message}", flush=True)
        else:
            print(f"🚫 Reading Error: {json.dumps(result, indent=2)}", flush=True)
    elif "writeToolCall" in tool_call:
        success = result.get("success", {})
        if success:
            message = success.get("message", "")
            print(f"🔧 Writing Done: {message}", flush=True)
        else:
            print(f"🚫 Writing Error: {json.dumps(result, indent=2)}", flush=True)
    elif "editToolCall" in tool_call:
        success = result.get("success", {})
        if success:
            message = success.get("message", "")
            print(f"🔧 Editing Done: {message}", flush=True)
        else:
            print(f"🚫 Editing Error: {json.dumps(result, indent=2)}", flush=True)
    elif "lsToolCall" in tool_call:
        success = result.get("success", {})
        if success:
            directoryTreeRoot = success.get("directoryTreeRoot", {})
            numFiles = directoryTreeRoot.get("numFiles", {})
            print(f"🔧 List Directory Done: {numFiles} files found", flush=True)
        else:
            failure = result.get("failure", {})
            print(f"🚫 List Directory Error: {json.dumps(failure, indent=2)}", flush=True)
    elif "shellToolCall" in tool_call:
        success = result.get("success", {})
        if success:
            commandText = result.get("success", "")
            executionTime = result.get("executionTime", "")
            print(f"🔧 Command Done: {commandText} in {executionTime} ms", flush=True)
        else:
            failure = result.get("failure", {})
            print(f"🚫 Command Error: {json.dumps(failure, indent=2)}", flush=True)
    elif "globToolCall" in tool_call:
        success = result.get("success", {})
        if success:
            totalFiles = success.get("totalFiles", 0)
            print(f"🚫 globToolCall Success: {totalFiles} totalFiles", flush=True)
    elif "function" in tool_call:
        name = tool_call["function"].get("name")
        result = tool_call.get("result", {})
        print(f"🛠️ Calling tool Done: {result}", flush=True)


def get_agent_processes() -> List[Dict[str, Any]]:
    """Lists all active agent-related processes (using tracking state and pgrep)."""
    # 1. Start with tracked agents
    active_tracked = agent_manager.get_active_agents()

    # 2. Augmented with pgrep to find floating ones
    stdout_vibe, _ = run_command(["pgrep", "-f", "vibe"], check=False)
    stdout_agent, _ = run_command(["pgrep", "-f", "agent"], check=False)

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
