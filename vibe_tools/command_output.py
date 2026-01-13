import sys
import threading
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

    def set_gui_callback(self, callback: Optional[Callable[[OutputMessage], None]]):
        self._gui_callback = callback

    def set_print_to_stdout(self, enabled: bool):
        self._print_to_stdout = enabled

    def log(self, message: str, level: str = "info", data: Optional[Any] = None, flush: bool = False):
        out_msg = OutputMessage(
            timestamp=datetime.now(),
            level=level,
            message=str(message),
            data=data
        )
        
        with self._lock:
            self._history.append(out_msg)
        
        if self._print_to_stdout:
            if flush:
                sys.stdout.write(str(message) + "\n")
                sys.stdout.flush()
            else:
                print(message)

        if self._gui_callback:
            try:
                self._gui_callback(out_msg)
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
