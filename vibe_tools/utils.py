import json
import logging
import os
import pathlib
import shutil
import signal
import subprocess
import sys
from typing import Any, Dict, List, Optional

from dotenv import find_dotenv, load_dotenv

from vibe_tools.command_output import out_info, out_success, out_warn, output_manager

load_dotenv(find_dotenv() or ".env")

RUNTIME_DIR_NAME = ".vibe-tools"
GLOBAL_VIBE_TOOLS_DIR = pathlib.Path.home() / ".vibe-tools"
GLOBAL_CONFIG_FILE = GLOBAL_VIBE_TOOLS_DIR / "config.json"
GLOBAL_SERVERS_FILE = GLOBAL_VIBE_TOOLS_DIR / "servers.json"
PROJECTS_REGISTRY_FILE = GLOBAL_VIBE_TOOLS_DIR / "projects.json"

VIBE_PROJECT_DIR = pathlib.Path(RUNTIME_DIR_NAME)
LOGS_DIR = VIBE_PROJECT_DIR / "logs"
COSTS_DIR = VIBE_PROJECT_DIR / "costs"
INSTRUCTIONS_DIR = VIBE_PROJECT_DIR / "instructions"
VIBE_DATA_DIR = VIBE_PROJECT_DIR / "data"
CONFIG_FILE = VIBE_PROJECT_DIR / "config.json"
RUN_PIDS_FILE = VIBE_PROJECT_DIR / "run-pids.json"

logger = logging.getLogger("vibe_tools")
logger.setLevel(logging.INFO)
logger.propagate = False


def is_test_mode() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules


def ensure_dir(path: pathlib.Path):
    path.mkdir(parents=True, exist_ok=True)


def _read_json(path: pathlib.Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: pathlib.Path, data: Any):
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def get_project_root() -> pathlib.Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        root = result.stdout.strip()
        if root:
            return pathlib.Path(root)
    except Exception:
        pass
    return pathlib.Path.cwd()


def get_project_name() -> str:
    return get_project_root().name or "project"


def _local_path(relative_path: pathlib.Path) -> pathlib.Path:
    return get_project_root() / relative_path


def _env_file() -> pathlib.Path:
    return get_project_root() / ".env"


def _read_env() -> Dict[str, str]:
    env_path = _env_file()
    values: Dict[str, str] = {}
    if not env_path.exists():
        return values
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


def _write_env(values: Dict[str, str]):
    env_path = _env_file()
    lines = [f"{key}={value}" for key, value in sorted(values.items())]
    env_path.write_text("\n".join(lines) + ("\n" if lines else ""))
    load_dotenv(env_path, override=True)


def load_config(global_scope: bool = False) -> Dict[str, Any]:
    global_config = _read_json(GLOBAL_CONFIG_FILE, {})
    if global_scope:
        return global_config
    local_config = _read_json(_local_path(CONFIG_FILE), {})
    merged = dict(global_config)
    merged.update(local_config)
    return merged


def save_config(config: Dict[str, Any], global_scope: bool = False):
    target = GLOBAL_CONFIG_FILE if global_scope else _local_path(CONFIG_FILE)
    _write_json(target, config)


def load_global_servers() -> Dict[str, Any]:
    return _read_json(GLOBAL_SERVERS_FILE, {})


def save_global_servers(servers: Dict[str, Any]):
    _write_json(GLOBAL_SERVERS_FILE, servers)


def run_command(
    command: List[str],
    check: bool = True,
    cwd: Optional[pathlib.Path] = None,
    env: Optional[Dict[str, str]] = None,
    bypass_safety: bool = False,
) -> tuple[str, int]:
    del bypass_safety
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
    )
    stdout = (result.stdout or "") + (result.stderr or "")
    if check and result.returncode != 0:
        raise RuntimeError(stdout.strip() or f"Command failed: {' '.join(command)}")
    return stdout, result.returncode


def _reset_logger_handlers():
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass


def setup_logging(command_name: str, log: bool = True):
    _reset_logger_handlers()

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.WARNING)
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(stream_handler)

    if log:
        log_dir = _local_path(LOGS_DIR)
        ensure_dir(log_dir)
        log_path = log_dir / f"{command_name}.log"
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(file_handler)
        output_manager.set_log_file(log_path)


def set_console_level(level: int):
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setLevel(level)


def enable_console_debug():
    logger.setLevel(logging.DEBUG)
    set_console_level(logging.DEBUG)


def load_pids():
    return _read_json(_local_path(RUN_PIDS_FILE), {})


def save_pids(pids):
    _write_json(_local_path(RUN_PIDS_FILE), pids)


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def get_agent_processes() -> List[Dict[str, Any]]:
    processes: List[Dict[str, Any]] = []
    for name, payload in load_pids().items():
        if isinstance(payload, int):
            payload = {"main_pid": payload}
        pid = payload.get("main_pid")
        if not pid or not _pid_exists(int(pid)):
            continue
        processes.append(
            {
                "name": name,
                "pid": int(pid),
                "command": payload.get("command", name),
                "tracked": True,
                "chat_id": payload.get("chat_id"),
            }
        )
    return sorted(processes, key=lambda item: item["pid"])


def cleanup_stale_processes() -> List[str]:
    killed: List[str] = []
    remaining: Dict[str, Any] = {}
    for name, payload in load_pids().items():
        if isinstance(payload, int):
            payload = {"main_pid": payload}
        pid = payload.get("main_pid")
        if not pid:
            continue
        pid = int(pid)
        if not _pid_exists(pid):
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            killed.append(name)
        except OSError:
            remaining[name] = payload
    save_pids(remaining)
    return killed


def get_google_api_key() -> Optional[str]:
    return os.environ.get("GOOGLE_API_KEY") or _read_env().get("GOOGLE_API_KEY")


def get_cursor_api_key() -> Optional[str]:
    return os.environ.get("CURSOR_API_KEY") or _read_env().get("CURSOR_API_KEY")


def save_google_api_key(api_key: str):
    values = _read_env()
    values["GOOGLE_API_KEY"] = api_key
    _write_env(values)


def save_cursor_api_key(api_key: str):
    values = _read_env()
    values["CURSOR_API_KEY"] = api_key
    _write_env(values)


def get_vibe_status_report() -> str:
    config = load_config()
    services = config.get("services", {})
    processes = get_agent_processes()
    project_root = get_project_root()
    lines = [
        "vibe-tools status",
        f"Project Root: {project_root}",
        f"Runtime Dir:  {project_root / VIBE_PROJECT_DIR}",
        f"Config File:  {project_root / CONFIG_FILE}",
        f"Logs Dir:     {project_root / LOGS_DIR}",
        f"Costs Dir:    {project_root / COSTS_DIR}",
        f"Services:     {len(services)} configured",
        f"Processes:    {len(processes)} tracked",
        f"Google API:   {'set' if get_google_api_key() else 'missing'}",
        f"Cursor API:   {'set' if get_cursor_api_key() else 'missing'}",
    ]
    if services:
        lines.append("")
        lines.append("Configured Services:")
        for name in sorted(services):
            service = services[name]
            lines.append(
                f"- {name}: {service.get('host', 'localhost')}:{service.get('port', 'n/a')}"
            )
    return "\n".join(lines)


def maybe_init_git():
    if (get_project_root() / ".git").exists():
        return


def save_memory(text: str) -> pathlib.Path:
    instructions_dir = _local_path(INSTRUCTIONS_DIR)
    ensure_dir(instructions_dir)
    slug = "-".join(text.lower().split())[:40] or "memory"
    path = instructions_dir / f"{slug}.txt"
    path.write_text(text)
    return path


def perform_basic_init():
    ensure_dir(_local_path(VIBE_PROJECT_DIR))
    ensure_dir(_local_path(LOGS_DIR))
    ensure_dir(_local_path(COSTS_DIR))
    ensure_dir(_local_path(INSTRUCTIONS_DIR))
    ensure_dir(_local_path(VIBE_DATA_DIR))
    if not _local_path(CONFIG_FILE).exists():
        save_config(
            {
                "agent": {"agent": "cursor-agent", "stream": False},
                "default_budget": 5.0,
                "services": {},
            }
        )
    maybe_init_git()


def is_tool_available(tool: str) -> bool:
    return shutil.which(tool) is not None


class GlobalProjectRegistry:
    @staticmethod
    def load() -> Dict[str, Any]:
        return _read_json(
            PROJECTS_REGISTRY_FILE,
            {"projects": [], "last_active_project_id": None},
        )

    @staticmethod
    def save(data: Dict[str, Any]):
        _write_json(PROJECTS_REGISTRY_FILE, data)

    @classmethod
    def list_projects(cls) -> List[Dict[str, Any]]:
        return cls.load().get("projects", [])

    @classmethod
    def add_project(cls, name: str, path: str):
        import uuid

        data = cls.load()
        projects = data.setdefault("projects", [])
        resolved_path = str(pathlib.Path(path).resolve())
        for project in projects:
            if project["path"] == resolved_path:
                project["name"] = name
                cls.save(data)
                return
        projects.append(
            {"id": str(uuid.uuid4()), "name": name, "path": resolved_path}
        )
        cls.save(data)

    @classmethod
    def remove_project(cls, name_or_id: str):
        data = cls.load()
        data["projects"] = [
            project
            for project in data.get("projects", [])
            if project["id"] != name_or_id and project["name"] != name_or_id
        ]
        cls.save(data)

    @classmethod
    def get_project_by_path(cls, path: str) -> Optional[Dict[str, Any]]:
        resolved_path = str(pathlib.Path(path).resolve())
        for project in cls.list_projects():
            if project["path"] == resolved_path:
                return project
        return None

    @classmethod
    def set_active_project(cls, project_id: Optional[str]):
        data = cls.load()
        data["last_active_project_id"] = project_id
        cls.save(data)
