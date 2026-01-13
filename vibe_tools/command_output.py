import sys
import threading
import pathlib
import json
from typing import List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime


@dataclass
class OutputMessage:
    timestamp: datetime
    level: str
    message: str
    data: Optional[Any] = None


class OutputManager:
    def __init__(self):
        self._history: List[OutputMessage] = []
        self._lock = threading.Lock()
        self._gui_callback: Optional[Callable[[OutputMessage], None]] = None
        self._print_to_stdout: bool = True
        self._log_file: Optional[pathlib.Path] = None
        self._md_log_file: Optional[pathlib.Path] = None

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
    ):
        out_msg = OutputMessage(
            timestamp=datetime.now(), level=level, message=str(message), data=data
        )

        with self._lock:
            self._history.append(out_msg)

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

        message_content = out_msg.message
        if "\n" in message_content:
            # Multi-line message as blockquote
            message_content = "\n" + "\n".join(
                [f"> {line}" for line in message_content.splitlines()]
            )

        md_entry = f"[{timestamp_str}] {level_fmt}: {message_content}\n"

        if out_msg.data:
            try:
                data_str = json.dumps(out_msg.data, indent=2)
                md_entry += f"\n```json\n{data_str}\n```\n"
            except (TypeError, ValueError):
                md_entry += f"\n```\n{str(out_msg.data)}\n```\n"

        md_entry += "\n---\n"

        try:
            with open(self._md_log_file, "a", encoding="utf-8") as f:
                f.write(md_entry)
        except Exception:
            pass

    def get_history(self) -> List[OutputMessage]:
        with self._lock:
            return list(self._history)


output_manager = OutputManager()


def out_print(message: str, level: str = "info", **kwargs):
    output_manager.log(message, level=level, **kwargs)


def out_info(message: str, **kwargs):
    output_manager.log(message, level="info", **kwargs)


def out_warn(message: str, **kwargs):
    output_manager.log(message, level="warning", **kwargs)


def out_error(message: str, **kwargs):
    output_manager.log(message, level="error", **kwargs)


def out_success(message: str, **kwargs):
    output_manager.log(message, level="success", **kwargs)


def out_debug(message: str, **kwargs):
    output_manager.log(message, level="debug", **kwargs)
