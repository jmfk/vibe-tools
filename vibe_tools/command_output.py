import sys
import threading
import pathlib
import json
import logging
from typing import List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime


@dataclass
class OutputMessage:
    timestamp: datetime
    level: str
    message: str
    source: str = "vibe"
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
        source: str = "vibe",
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

        if out_msg.data:
            try:
                data_str = json.dumps(out_msg.data, indent=2)
                md_entry += f">\n> ```json\n"
                for line in data_str.splitlines():
                    md_entry += f"> {line}\n"
                md_entry += f"> ```\n"
            except (TypeError, ValueError):
                md_entry += f">\n> ```\n"
                for line in str(out_msg.data).splitlines():
                    md_entry += f"> {line}\n"
                md_entry += f"> ```\n"

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


def out_error(message: str, source: str = "vibe", **kwargs):
    output_manager.log(message, level="error", source=source, **kwargs)


def out_success(message: str, source: str = "vibe", **kwargs):
    output_manager.log(message, level="success", source=source, **kwargs)


def out_debug(message: str, source: str = "vibe", **kwargs):
    output_manager.log(message, level="debug", source=source, **kwargs)
