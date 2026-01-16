import sys
import threading
import pathlib
import json
import logging
import html
import re
from typing import List, Optional, Any, Callable, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class OutputMessage:
    timestamp: datetime
    level: str
    message: str
    source: str = "vibe"
    data: Optional[Any] = None


class JSONStream:
    def __init__(self, manager):
        self.manager = manager
        self.buffer = ""

    def write(self, data):
        if not data:
            return
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        self.buffer += data
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if line.strip():
                self.manager.log(line, level="info", source="stdout")

    def flush(self):
        if self.buffer.strip():
            self.manager.log(self.buffer, level="info", source="stdout")
            self.buffer = ""


class OutputManager:
    def __init__(self):
        self._history: List[OutputMessage] = []
        self._lock = threading.Lock()
        self._gui_callback: Optional[Callable[[OutputMessage], None]] = None
        self._print_to_stdout: bool = True
        self._log_file: Optional[pathlib.Path] = None
        self._md_log_file: Optional[pathlib.Path] = None
        self._config: Dict[str, Any] = {}
        self._server_mode: bool = False
        self._input_queue = []
        self._input_event = threading.Event()
        self._stop_listener = threading.Event()
        self._listener_thread: Optional[threading.Thread] = None
        self._real_stdout = sys.stdout
        self._final_code = 0
        self._final_data = {}

    def set_final_result(self, code: int, data: Dict[str, Any] = None):
        self._final_code = code
        if data:
            self._final_data.update(data)

    def get_final_result(self) -> Tuple[int, Dict[str, Any]]:
        return self._final_code, self._final_data

    def set_server_mode(self, enabled: bool):
        self._server_mode = enabled
        if enabled:
            self._print_to_stdout = False
            self._real_stdout = sys.stdout
            # Use JSONStream to capture any direct prints to stdout
            sys.stdout = JSONStream(self)
            self.start_stdin_listener()

    def start_stdin_listener(self):
        if self._listener_thread and self._listener_thread.is_alive():
            return

        self._stop_listener.clear()
        self._listener_thread = threading.Thread(
            target=self._stdin_listener_loop, daemon=True
        )
        self._listener_thread.start()

    def _stdin_listener_loop(self):
        while not self._stop_listener.is_set():
            line = sys.stdin.readline()
            if not line:
                break

            try:
                data = json.loads(line)
                msg_type = data.get("type")

                if msg_type == "cancel":
                    # Handle cancellation
                    from vibe_tools.agent import agent_manager
                    import _thread

                    agent_manager.cleanup_session()
                    self.set_final_result(0, {"status": "cancelled"})
                    # Signal the main thread to exit
                    _thread.interrupt_main()
                elif msg_type == "input":
                    value = data.get("value")
                    with self._lock:
                        self._input_queue.append(value)
                        self._input_event.set()
                elif msg_type == "prompt_response":
                    value = data.get("value")
                    with self._lock:
                        self._input_queue.append(value)
                        self._input_event.set()
            except Exception as e:
                # In server mode, we should probably log this as an error object
                if not self._server_mode:
                    print(f"Error parsing STDIN JSON: {e}", file=sys.stderr)

    def get_input(self, prompt_message: str = None) -> str:
        if self._server_mode:
            if prompt_message:
                self.emit_server_message("prompt", {"message": prompt_message})

            self._input_event.wait()
            with self._lock:
                if self._input_queue:
                    val = self._input_queue.pop(0)
                    if not self._input_queue:
                        self._input_event.clear()
                    return val
            return ""
        else:
            import click

            return click.prompt(prompt_message) if prompt_message else input()

    def emit_server_message(self, msg_type: str, data: Dict[str, Any]):
        if self._server_mode:
            payload = {"type": msg_type}
            payload.update(data)
            self._real_stdout.write(json.dumps(payload) + "\n")
            self._real_stdout.flush()

    def set_config(self, config: Dict[str, Any]):
        """Sets the configuration for the output manager."""
        self._config = config

    def set_gui_callback(self, callback: Optional[Callable[[OutputMessage], None]]):
        self._gui_callback = callback

    def set_print_to_stdout(self, enabled: bool):
        self._print_to_stdout = enabled

    def set_log_file(self, path: pathlib.Path):
        """Sets the base log file path and derives the markdown log file path."""
        self._log_file = path
        self._md_log_file = path.with_suffix(".md")

        # Ensure the directory exists
        self._md_log_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize the markdown file with a header if it's new
        if not self._md_log_file.exists():
            self._md_log_file.write_text(
                f"# Session Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )

    def log(
        self,
        message: str,
        level: str = "info",
        data: Optional[Any] = None,
        flush: bool = False,
        source: str = "vibe",
        traceback: Optional[str] = None,
    ):
        out_msg = OutputMessage(
            timestamp=datetime.now(),
            level=level,
            message=str(message),
            data=data,
            source=source,
        )

        with self._lock:
            self._history.append(out_msg)

        if self._server_mode:
            # In server mode, only emit errors by default.
            # Don't emit debug/info logs unless specifically requested via a flag (not yet implemented)
            # or if it's an error.
            if level == "error":
                self.emit_server_message(
                    "error",
                    {
                        "message": str(message),
                        "traceback": traceback,
                        "timestamp": out_msg.timestamp.isoformat(),
                    },
                )
            elif level in ("info", "success", "warning"):
                # Still allow info/success/warning logs in server mode
                self.emit_server_message(
                    "log",
                    {
                        "level": level,
                        "source": source,
                        "message": str(message),
                        "timestamp": out_msg.timestamp.isoformat(),
                        "data": data,
                    },
                )
            # Note: "debug" level is suppressed in server mode

        if self._print_to_stdout:
            if flush:
                sys.stdout.write(str(message) + "\n")
                sys.stdout.flush()
            else:
                print(message)

        if self._md_log_file:
            self._write_to_md_log(out_msg)

        if self._gui_callback:
            try:
                self._gui_callback(out_msg)
            except Exception:
                pass

    def _write_to_md_log(self, out_msg: OutputMessage):
        """Formats and appends the message to the markdown log file."""
        if not self._md_log_file:
            return

        timestamp_str = out_msg.timestamp.strftime("%H:%M:%S")
        level_upper = out_msg.level.upper()

        # Use different formatting based on level
        if out_msg.level == "error":
            level_fmt = f"❌ **{level_upper}**"
        elif out_msg.level == "warning":
            level_fmt = f"⚠️ **{level_upper}**"
        elif out_msg.level == "success":
            level_fmt = f"✅ **{level_upper}**"
        elif out_msg.level == "debug":
            level_fmt = f"🔍 *{level_upper}*"
        else:
            level_fmt = f"**{level_upper}**"

        # Determine callout type based on source
        # source="vibe": > [!NOTE]
        # source="llm": > [!TIP]
        # source="agent": > [!IMPORTANT]
        callout_type = "NOTE"
        if out_msg.source == "llm":
            callout_type = "TIP"
        elif out_msg.source == "agent":
            callout_type = "IMPORTANT"

        message_content = out_msg.message

        # Format the entry with callout
        md_entry = f"> [!{callout_type}]\n"
        md_entry += f"> [{timestamp_str}] {level_fmt}\n>\n"

        for line in message_content.splitlines():
            md_entry += f"> {line}\n"

        # Handle EVENT: ... -> See ... and include HTML logs if enabled
        include_html = self._config.get("ralph", {}).get("include_html_logs", False)
        if include_html and "EVENT:" in message_content and "-> See" in message_content:
            # Extract the path from "EVENT: event_name -> See path"
            match = re.search(r"EVENT: (.*?) -> See (.*)$", message_content)
            if match:
                event_name = match.group(1).strip()
                ref_path_str = match.group(2).strip()
                ref_path = pathlib.Path(ref_path_str)

                if ref_path.exists():
                    try:
                        content = ref_path.read_text(encoding="utf-8")

                        md_entry += ">\n"
                        md_entry += "> <details>\n"
                        md_entry += f"> <summary>{event_name}</summary>\n"
                        md_entry += ">\n"
                        md_entry += "> ```\n"
                        for line in content.splitlines():
                            md_entry += f"> {line}\n"
                        md_entry += "> ```\n"
                        md_entry += "> </details>\n"
                    except Exception as e:
                        md_entry += f">\n> *Could not include content: {e}*\n"

        if out_msg.data:
            try:
                data_str = json.dumps(out_msg.data, indent=2)
                md_entry += ">\n> ```json\n"
                for line in data_str.splitlines():
                    md_entry += f"> {line}\n"
                md_entry += "> ```\n"
            except (TypeError, ValueError):
                md_entry += ">\n> ```\n"
                for line in str(out_msg.data).splitlines():
                    md_entry += f"> {line}\n"
                md_entry += "> ```\n"

        md_entry += "\n---\n"

        try:
            with open(self._md_log_file, "a", encoding="utf-8") as f:
                f.write(md_entry)
        except Exception:
            pass

    def get_history(self) -> List[OutputMessage]:
        with self._lock:
            return list(self._history)


class OutputManagerHandler(logging.Handler):
    """Logging handler that redirects records to an OutputManager."""

    def __init__(self, manager: OutputManager):
        super().__init__()
        self.manager = manager

    def emit(self, record):
        try:
            msg = self.format(record)
            level = record.levelname.lower()
            if level == "critical":
                level = "error"
            # Standard logger calls are treated as "vibe" source
            self.manager.log(msg, level=level, source="vibe")
        except Exception:
            self.handleError(record)


output_manager = OutputManager()


def out_print(message: str, level: str = "info", **kwargs):
    output_manager.log(message, level=level, **kwargs)


def out_info(message: str, source: str = "vibe", **kwargs):
    output_manager.log(message, level="info", source=source, **kwargs)


def out_warn(message: str, source: str = "vibe", **kwargs):
    output_manager.log(message, level="warning", source=source, **kwargs)


def out_error(message: str, source: str = "vibe", traceback: Optional[str] = None, **kwargs):
    output_manager.log(message, level="error", source=source, traceback=traceback, **kwargs)


def out_success(message: str, source: str = "vibe", **kwargs):
    output_manager.log(message, level="success", source=source, **kwargs)


def out_debug(message: str, source: str = "vibe", **kwargs):
    output_manager.log(message, level="debug", source=source, **kwargs)


def out_status(phase: str, status: str, progress: int = 0, **kwargs):
    """Emits a status update message (primarily for server mode)."""
    output_manager.emit_server_message(
        "status", {"phase": phase, "status": status, "progress": progress, **kwargs}
    )


def vibe_prompt(message: str, **kwargs) -> str:
    """A wrapper around click.prompt that supports server mode."""
    return output_manager.get_input(message)
