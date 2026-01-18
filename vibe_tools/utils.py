import datetime
import functools
import hashlib
import importlib.util
import json
import logging
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional, Tuple

import yaml
from dotenv import find_dotenv, set_key

from vibe_tools.command_output import (
    out_debug,
    out_error,
    out_info,
    out_success,
    out_warn,
    out_print as out_print,
    output_manager,
)

VIBE_PROJECT_DIR = pathlib.Path("implementation")
PRODUCT_DIR = pathlib.Path("product")
PLANNING_DIR = PRODUCT_DIR

# Product Planning (Markdown)
PRODUCT_BACKLOG_DIR = PRODUCT_DIR / "backlog"
PRODUCT_IN_PROGRESS_DIR = PRODUCT_DIR / "in_progress"
PRODUCT_HISTORY_DIR = PRODUCT_DIR / "history"
PLANNING_INBOX_DIR = PRODUCT_DIR / "inbox"
PRODUCT_NEXT_DIR = PRODUCT_DIR / "next"
PLANNING_BACKLOG_DIR = PRODUCT_BACKLOG_DIR
PLANNING_HISTORY_DIR = PRODUCT_HISTORY_DIR
PLANNING_REJECTED_DIR = PRODUCT_DIR / "rejected"

# Implementation state
PROJECT_STATE_FILE = VIBE_PROJECT_DIR / "state.json"
STATE_FILE = VIBE_PROJECT_DIR / "legacy-state.json"
LOGS_DIR = VIBE_PROJECT_DIR / "logs"
COSTS_DIR = VIBE_PROJECT_DIR / "costs"
INSTRUCTIONS_DIR = VIBE_PROJECT_DIR / "instructions"
KNOWLEDGE_DIR = VIBE_PROJECT_DIR / "knowledge"
VIBE_DATA_DIR = VIBE_PROJECT_DIR / "data"
CONFIG_FILE = VIBE_PROJECT_DIR / "config.json"
GLOBAL_VIBE_DIR = pathlib.Path.home() / ".vibe"

# Core lifecycle files
ARCHITECTURE_CURRENT = VIBE_PROJECT_DIR / "architecture-current.yaml"
# ... (rest of files)

SENSITIVE_KEYS = {
    "GOOGLE_API_KEY",
    "CURSOR_API_KEY",
    "GITHUB_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "STRIPE_SECRET_KEY",
    "DATABASE_URL",
}
ARCHITECTURE_SPEC = PLANNING_DIR / "SRD-architecture.md"
OVERVIEW_SPEC = PLANNING_DIR / "SRD-project_overview.md"
INFRA_CURRENT = VIBE_PROJECT_DIR / "infrastructure-current.yaml"
INFRA_SPEC = PLANNING_DIR / "SRD-infrastructure.md"
CICD_CURRENT = VIBE_PROJECT_DIR / "cicd-current.yaml"
CICD_SPEC = PLANNING_DIR / "SRD-cicd.md"
TESTING_CURRENT = VIBE_PROJECT_DIR / "testing-current.yaml"
TESTING_SPEC = PLANNING_DIR / "SRD-testing.md"
DEV_ENV_CURRENT = VIBE_PROJECT_DIR / "dev_environment-current.yaml"
DEV_SPEC = PLANNING_DIR / "SRD-dev_environment.md"
SETUP_SPEC = PLANNING_DIR / "SRD-setup.md"

GLOBAL_CONFIG_FILE = GLOBAL_VIBE_DIR / "config.json"
GLOBAL_VIBE_TOOLS_DIR = pathlib.Path.home() / ".vibe-tools"
PROJECTS_REGISTRY_FILE = GLOBAL_VIBE_TOOLS_DIR / "projects.json"
ARCH_CONFIG_FILE = VIBE_PROJECT_DIR / "architect-config.json"
ARCH_SESSION_FILE = VIBE_PROJECT_DIR / "architect-session.json"
PM_CONFIG_FILE = VIBE_PROJECT_DIR / "pm-config.json"
PM_SESSION_FILE = VIBE_PROJECT_DIR / "pm-session.json"
SPECS_DIR = PLANNING_DIR
GLOBAL_SERVERS_FILE = GLOBAL_VIBE_DIR / "servers.json"

# --- Logging Setup ---
logger = logging.getLogger("vibe_tools")
LOG_SESSION_DIR: Optional[pathlib.Path] = None
_log_counter = 0


def log_large_output(event_name: str, content: str) -> Optional[pathlib.Path]:
    """Writes multi-row output to a separate numbered file in the session directory."""
    global _log_counter, LOG_SESSION_DIR
    if not content or not content.strip():
        return None

    _log_counter += 1

    if LOG_SESSION_DIR is None:
        # Fallback if logging wasn't set up via setup_logging
        # LOG_SESSION_DIR = LOGS_DIR
        return None

    ensure_dir(LOG_SESSION_DIR)

    # Create a safe filename from the event name
    slug = "".join(c if c.isalnum() else "_" for c in event_name[:30]).lower()
    filename = f"{_log_counter:03d}_{slug}.txt"
    filepath = LOG_SESSION_DIR / filename

    filepath.write_text(content)

    # Log only the event "pointer" to the main log file
    try:
        rel_path = filepath.relative_to(pathlib.Path.cwd())
    except ValueError:
        rel_path = filepath

    out_info(f"EVENT: {event_name} -> See {rel_path}", data=content)

    return filepath


@functools.lru_cache(maxsize=1)
def is_git_repo():
    """Checks if the current directory is a git repository."""
    try:
        curr = pathlib.Path.cwd()
        for parent in [curr] + list(curr.parents):
            if (parent / ".git").exists():
                return True
        return False
    except Exception:
        return False


def is_test_mode() -> bool:
    """Checks if the system is running in test mode."""
    return os.environ.get("VIBE_TEST_MODE") == "1" or "pytest" in sys.modules


def get_last_commit_hash() -> Optional[str]:
    """Retrieves the current HEAD commit hash."""
    stdout, code = run_command(["git", "rev-parse", "HEAD"], check=False)
    if code == 0:
        return stdout.strip()
    return None


def run_command(
    command: List[str],
    cwd: Optional[str] = None,
    check: bool = True,
) -> Tuple[str, int]:
    """Runs a shell command and returns its stdout and exit code."""
    if is_test_mode():
        intrusive_commands = {
            "make",
            "docker",
            "skaffold",
            "helm",
            "pip",
            "npm",
            "npx",
            "uvicorn",
            "pytest",
            "python",
        }
        main_cmd = command[0] if command else ""
        if main_cmd in intrusive_commands:
            logger.warning(
                f"Blocking intrusive command in test mode: {' '.join(command)}"
            )
            return f"Blocked intrusive command: {' '.join(command)}", 0

    try:
        # Log the command execution details
        out_debug(
            f"Running command: {' '.join(command)}",
            source="vibe",
            data={
                "command": command,
                "cwd": cwd or os.getcwd(),
            },
        )

        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=check,
        )
        if len(result.stdout.splitlines()) > 5:
            log_large_output(f"command_{command[0]}", result.stdout)

        # Log successful completion with output summary if needed
        out_debug(
            f"Command {command[0]} finished (code: {result.returncode})",
            source="vibe",
            data={
                "command_line": f"$ {' '.join(command)}",
                "stdio": "",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "code": result.returncode,
            },
        )

        return result.stdout, result.returncode
    except subprocess.CalledProcessError as e:
        output = (e.stdout or "") + (e.stderr or "")
        if len(output.splitlines()) > 5:
            log_large_output(f"command_{command[0]}_error", output)

        # Log failure
        out_error(
            f"Command {command[0]} failed (code: {e.returncode})",
            source="vibe",
            data={
                "command_line": f"$ {' '.join(command)}",
                "stdio": "",
                "stdout": e.stdout,
                "stderr": e.stderr,
                "code": e.returncode,
            },
        )

        return output, e.returncode
    except (FileNotFoundError, OSError) as e:
        out_error(
            f"Command {command[0]} could not be executed: {e}",
            source="vibe",
            data={
                "command_line": f"$ {' '.join(command)}",
                "stdio": "",
                "stdout": "",
                "stderr": str(e),
                "error": str(e),
            },
        )
        return str(e), 127


def get_main_branch() -> str:
    """Determines the main branch of the repository (main or master)."""
    stdout, code = run_command(["git", "branch", "--list"], check=False)
    if code == 0:
        if "main" in stdout:
            return "main"
        if "master" in stdout:
            return "master"
    return "main"


def get_automerge_branch(config: Dict[str, Any]) -> str:
    """Determines the target branch for auto-merging."""
    return config.get("ralph", {}).get("automerge_branch", get_main_branch())


def get_file_hash(path: pathlib.Path) -> str:
    """Computes the SHA-256 hash of a file."""
    if not path.exists():
        return ""
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def ensure_dir(path: pathlib.Path):
    """Ensures a directory exists."""
    path.mkdir(parents=True, exist_ok=True)


def load_config(global_scope: bool = False) -> Dict[str, Any]:
    """Loads the project or global configuration."""
    target = GLOBAL_CONFIG_FILE if global_scope else CONFIG_FILE
    if target.exists():
        try:
            config = json.loads(target.read_text())
            # DEFENSIVE: Never return envs/vars from config.json
            if not global_scope:
                for key in ["envs", "env", "vars", "current_env"]:
                    if key in config:
                        del config[key]
            return config
        except json.JSONDecodeError:
            return {}
    return {}


def save_config(config: Dict[str, Any], global_scope: bool = False):
    """Saves the project or global configuration."""
    # Never save envs or vars to config.json
    if not global_scope:
        for key in ["envs", "env", "vars", "current_env"]:
            if key in config:
                del config[key]

    target = GLOBAL_CONFIG_FILE if global_scope else CONFIG_FILE
    ensure_dir(target.parent)
    target.write_text(json.dumps(config, indent=2))


def load_project_state() -> Dict[str, Any]:
    """Loads the current project state from state.json."""
    state = {
        "phases": {
            "setup": {"status": "pending", "hash": ""},
            "implement": {"status": "pending"},
            "testing": {"status": "pending"},
            "deploy": {"status": "pending"},
        },
        "completed_prds": [],
        "started_prds": [],
        "plans": {},
    }

    if PROJECT_STATE_FILE.exists():
        try:
            loaded = json.loads(PROJECT_STATE_FILE.read_text())
            # Deep merge phases to avoid losing defaults if state.json is partial
            if "phases" in loaded:
                for phase_id, phase_data in loaded.pop("phases").items():
                    if phase_id in state["phases"]:
                        state["phases"][phase_id].update(phase_data)
                    else:
                        state["phases"][phase_id] = phase_data
            state.update(loaded)
        except json.JSONDecodeError:
            pass

    # Dynamically compute completed_prds and started_prds from filesystem
    if PRODUCT_HISTORY_DIR.exists():
        completed = []
        for f in PRODUCT_HISTORY_DIR.glob("*.md"):
            # Extract PRD-NNN or similar from filename
            match = re.search(
                r"(PRD-\d+|SRD-[a-z0-9_-]+|ISSUE-[a-z0-9_-]+)", f.name, re.IGNORECASE
            )
            if match:
                completed.append(match.group(1))
            else:
                completed.append(f.stem)
        state["completed_prds"] = sorted(list(set(completed)))

    if PRODUCT_IN_PROGRESS_DIR.exists():
        started = []
        for f in PRODUCT_IN_PROGRESS_DIR.glob("*.md"):
            match = re.search(
                r"(PRD-\d+|SRD-[a-z0-9_-]+|ISSUE-[a-z0-9_-]+)", f.name, re.IGNORECASE
            )
            if match:
                started.append(match.group(1))
            else:
                started.append(f.stem)
        state["started_prds"] = sorted(list(set(started)))

    return state


def save_project_state(state: Dict[str, Any]):
    """Saves the current project state to state.json."""
    ensure_dir(VIBE_PROJECT_DIR)

    # Don't save dynamic lists to the file to favor filesystem-based truth
    to_save = state.copy()
    if "completed_prds" in to_save:
        to_save["completed_prds"] = []
    if "started_prds" in to_save:
        to_save["started_prds"] = []

    PROJECT_STATE_FILE.write_text(json.dumps(to_save, indent=2))


def is_branch_switching_enabled() -> bool:
    """Checks if automatic branch switching is enabled."""
    import click

    # Check Click context first if available
    try:
        ctx = click.get_current_context(silent=True)
        if ctx and ctx.obj and ctx.obj.get("no_branch_switch"):
            return False
    except Exception:
        pass

    # Fallback to config
    config = load_config()
    if config.get("no_branch_switch") or config.get("ralph", {}).get(
        "no_branch_switch"
    ):
        return False

    return True


def check_dependencies(phase: str, state: Dict[str, Any]) -> List[str]:
    """Checks if the dependencies for a given phase are met."""
    dependencies = {
        "normalize": [],
        "setup": [],
        "deps": ["setup"],
        "implement": ["setup"],
        "testing": ["implement"],
        "infra": ["setup"],
        "deploy": ["testing"],
    }

    missing = []
    for dep in dependencies.get(phase, []):
        if dep == "setup":
            if state["phases"]["setup"]["status"] != "completed":
                missing.append("setup (vibe setup)")
        elif dep == "implement":
            if state["phases"]["implement"]["status"] != "completed":
                missing.append("implement (vibe implement)")
        elif dep == "testing":
            if state["phases"]["testing"]["status"] != "completed":
                missing.append("testing (vibe testing)")

    return missing


def diagnose_setup_failure() -> str:
    """Provides a detailed diagnostic message for setup failures."""
    import click

    messages = []

    if not ARCHITECTURE_SPEC.exists():
        messages.append(
            f"❌ {click.style(ARCHITECTURE_SPEC.name, fg='yellow')} is missing."
        )
        messages.append(
            f"   Run {click.style('vibe architect', fg='cyan')} to define your architecture or {click.style('vibe init', fg='cyan')} to start fresh."
        )
    elif not ARCHITECTURE_CURRENT.exists():
        messages.append(
            f"❌ {click.style(ARCHITECTURE_CURRENT.name, fg='yellow')} is missing."
        )
        messages.append(
            f"   Run {click.style('vibe setup --import-code', fg='cyan')} if you have an existing codebase, or {click.style('vibe setup', fg='cyan')} to initialize it."
        )
    else:
        messages.append(f"⚠️  Architecture reconciliation is pending.")
        messages.append(
            f"   Run {click.style('vibe setup', fg='cyan')} to reconcile {ARCHITECTURE_SPEC.name} with {ARCHITECTURE_CURRENT.name}."
        )

    return "\n".join(messages)


# Global handlers for console and file
stream_handler: Optional[logging.StreamHandler] = None
file_handler: Optional[RotatingFileHandler] = None


def rotate_log():
    """Manually rotates the log file if it exists and is not empty."""
    global file_handler
    if (
        file_handler
        and os.path.exists(file_handler.baseFilename)
        and os.path.getsize(file_handler.baseFilename) > 0
    ):
        file_handler.doRollover()


def setup_logging(command_name: str, log: bool = True):
    """Configures logging for a CLI command."""
    global stream_handler, file_handler, LOG_SESSION_DIR

    # Root logger configuration
    logger = logging.getLogger("vibe_tools")
    logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers if setup_logging is called multiple times
    if logger.handlers:
        return logger

    if log:
        ensure_dir(LOGS_DIR)

        # Add datetime prefix to log filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOGS_DIR / f"{timestamp}_{command_name}.log"

        # Set the directory for multi-row outputs
        LOG_SESSION_DIR = LOGS_DIR / f"{timestamp}_{command_name}"

        # Initialize OutputManager with the log file
        output_manager.set_log_file(log_file)

        # File handler (always DEBUG level)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Pass config to output_manager
    config = load_config()
    output_manager.set_config(config)

    # Console handler (default to INFO, but WARNING in server mode)
    stream_handler = logging.StreamHandler()
    if "--server" in sys.argv:
        stream_handler.setLevel(logging.WARNING)
    else:
        stream_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(message)s")
    stream_handler.setFormatter(console_formatter)
    logger.addHandler(stream_handler)

    # OutputManager handler (captures logger.info, etc. to MD log)
    from vibe_tools.command_output import OutputManagerHandler

    om_handler = OutputManagerHandler(output_manager)
    om_handler.setLevel(logging.INFO)
    # Don't set a formatter here, let the handler use the raw message or
    # we'll get double formatting in MD log.
    logger.addHandler(om_handler)

    return logger


def set_console_level(level: int):
    """Updates the log level for the console handler."""
    global stream_handler
    if stream_handler:
        stream_handler.setLevel(level)
    else:
        # Fallback to searching handlers
        logger = logging.getLogger("vibe_tools")
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(level)

    # Also ensure the logger itself allows this level
    logger = logging.getLogger("vibe_tools")
    if logger.level > level or logger.level == logging.NOTSET:
        logger.setLevel(level)


def enable_console_debug():
    """Enables DEBUG level logging for the console handler."""
    set_console_level(logging.DEBUG)


LOG_FILE = LOGS_DIR / "vibe.log"


def get_prompt(filename: str) -> str:
    """Retrieves a prompt template from the prompts/ directory or system defaults."""
    # 1. Check project prompts directory
    project_prompt = pathlib.Path("prompts") / filename
    if project_prompt.exists():
        return project_prompt.read_text()

    # 2. Fallback to package TEMPLATES
    from vibe_tools.templates import TEMPLATES

    if filename in TEMPLATES:
        return TEMPLATES[filename]

    # 3. Fallback to package resources (deprecated/legacy check)
    try:
        # We can't import .prompts because it doesn't exist.
        # This was likely intended for when prompts were package data.
        # For now, we'll just raise the error if not found in TEMPLATES or filesystem.
        raise FileNotFoundError
    except (ImportError, FileNotFoundError):
        raise FileNotFoundError(f"Prompt template '{filename}' not found.")


def get_agent_command(agent: str, prompt: str) -> List[str]:
    """Constructs the command to invoke the specified AI agent."""
    from .agent import get_agent_command as _get_agent_command

    return _get_agent_command(agent, prompt)


def run_agent(command: List[str], stream: bool = False) -> Tuple[str, int]:
    """Runs an agent command, optionally preventing sleep and streaming output."""
    from .agent import run_agent as _run_agent

    output, code, _ = _run_agent(command, stream=stream)

    return output, code


def safe_yaml_load(content: str) -> Any:
    """Safely loads YAML content, returning None on error."""
    try:
        return yaml.safe_load(content)
    except yaml.YAMLError:
        return None


def safe_yaml_dump(data: Any) -> str:
    """Safely dumps data to YAML string."""
    return yaml.safe_dump(data, sort_keys=False)


def collect_all_prd_info() -> List[Dict[str, Any]]:
    """Collects status information for all PRDs (Markdown only)."""
    prds = {}

    # Look for human specs in product/
    if PLANNING_DIR.exists():
        for f in PLANNING_DIR.rglob("*.md"):
            name = f.stem
            if name.startswith("SRD-") or name in [
                "architecture",
                "infrastructure",
                "cicd",
                "testing",
                "dev_environment",
                "project-overview",
                "project_overview",
                "setup",
                "widgets",
            ]:
                continue
            prds[name] = {
                "name": name,
                "has_md": True,
                "md_path": f,
                "has_yaml": False,
                "yaml_path": None,
            }

    return sorted(list(prds.values()), key=lambda x: x["name"])


def reset_prd_state(project_name: str) -> List[str]:
    """Resets the state of a PRD, allowing it to be rerun."""
    messages = []
    state = load_project_state()

    # 1. Reset progress flags in the PRD file itself if possible
    from vibe_tools.prds import load_prd

    potential_files = list(PRODUCT_DIR.rglob(f"*{project_name}*.md"))
    if not potential_files:
        # Fallback to stem match if full name doesn't match
        potential_files = [
            f for f in PRODUCT_DIR.rglob("*.md") if project_name in f.name
        ]

    for f in potential_files:
        try:
            # If it was in history, move it back to backlog
            if "history" in str(f):
                new_path = PRODUCT_BACKLOG_DIR / f.name
                f.rename(new_path)
                f = new_path
                messages.append(f"Moved '{project_name}' from history back to backlog.")

            prd = load_prd(f)
            prd.reset_progress()
            prd.save()
            messages.append(f"Reset implementation progress flags for '{prd.id}'.")
        except Exception as e:
            messages.append(f"Could not reset PRD progress flags: {e}")

    # 2. Reset plan status in state.json
    plans = state.get("plans", {})
    if project_name in plans:
        plans[project_name]["status"] = "pending"
        messages.append(f"Reset plan status for '{project_name}' to pending.")

        # 3. Delete the implementation branch if it exists
        branch_name = plans[project_name].get("branch")
        if branch_name:
            stdout, code = run_command(
                ["git", "branch", "-D", branch_name], check=False
            )
            if code == 0:
                messages.append(f"Deleted local branch '{branch_name}'.")

    # Clean up static lists to favor dynamic ones
    if "completed_prds" in state:
        state["completed_prds"] = []
    if "started_prds" in state:
        state["started_prds"] = []

    save_project_state(state)
    return messages


def ensure_gitignore(patterns: List[str]):
    """Ensures that specified patterns are present in .gitignore."""
    gitignore = pathlib.Path(".gitignore")
    if not gitignore.exists():
        gitignore.write_text("\n".join(patterns) + "\n")
        return

    content = gitignore.read_text()
    lines = content.splitlines()
    new_patterns = [p for p in patterns if p not in lines]

    if new_patterns:
        with gitignore.open("a") as f:
            if not content.endswith("\n"):
                f.write("\n")
            for p in new_patterns:
                f.write(f"{p}\n")


class GlobalProjectRegistry:
    """Manages the global registry of vibe projects in ~/.vibe-tools/projects.json."""

    @staticmethod
    def load() -> Dict[str, Any]:
        """Loads the project registry."""
        if PROJECTS_REGISTRY_FILE.exists():
            try:
                return json.loads(PROJECTS_REGISTRY_FILE.read_text())
            except json.JSONDecodeError:
                pass
        return {"projects": [], "last_active_project_id": None}

    @staticmethod
    def save(registry: Dict[str, Any]):
        """Saves the project registry."""
        ensure_dir(GLOBAL_VIBE_TOOLS_DIR)
        PROJECTS_REGISTRY_FILE.write_text(json.dumps(registry, indent=2))

    @classmethod
    def add_project(
        cls,
        name: str,
        path: str,
        description: str = "",
        metadata: Dict[str, Any] = None,
        secrets: Dict[str, str] = None,
    ):
        """Adds or updates a project in the registry."""
        registry = cls.load()
        path = str(pathlib.Path(path).resolve())

        # Check if project already exists by path
        existing = next((p for p in registry["projects"] if p["path"] == path), None)

        if existing:
            existing["name"] = name
            existing["description"] = description
            existing["metadata"].update(metadata or {})
            existing["secrets"].update(secrets or {})
            existing["last_active"] = datetime.datetime.now().isoformat()
            registry["last_active_project_id"] = existing["id"]
        else:
            import uuid

            new_project = {
                "id": str(uuid.uuid4()),
                "name": name,
                "path": path,
                "description": description,
                "metadata": metadata or {},
                "secrets": secrets or {},
                "last_active": datetime.datetime.now().isoformat(),
            }
            registry["projects"].append(new_project)
            registry["last_active_project_id"] = new_project["id"]

        cls.save(registry)

    @classmethod
    def remove_project(cls, name_or_id: str):
        """Removes a project from the registry."""
        registry = cls.load()
        registry["projects"] = [
            p
            for p in registry["projects"]
            if p["id"] != name_or_id and p["name"] != name_or_id
        ]
        cls.save(registry)

    @classmethod
    def list_projects(cls) -> List[Dict[str, Any]]:
        """Lists all registered projects."""
        return cls.load()["projects"]

    @classmethod
    def get_project_by_path(cls, path: str) -> Optional[Dict[str, Any]]:
        """Finds a project by its path or any parent path."""
        registry = cls.load()
        target_path = pathlib.Path(path).resolve()

        # Sort projects by path length (deepest first) to match most specific project
        sorted_projects = sorted(
            registry["projects"],
            key=lambda p: len(pathlib.Path(p["path"]).parts),
            reverse=True,
        )

        for project in sorted_projects:
            project_path = pathlib.Path(project["path"]).resolve()
            try:
                # Check if target_path is project_path or a subdirectory
                if target_path == project_path or project_path in target_path.parents:
                    return project
            except ValueError:
                continue
        return None

    @classmethod
    def set_active_project(cls, project_id: str):
        """Sets the last active project."""
        registry = cls.load()
        project = next((p for p in registry["projects"] if p["id"] == project_id), None)
        if project:
            project["last_active"] = datetime.datetime.now().isoformat()
            registry["last_active_project_id"] = project_id
            cls.save(registry)


def ensure_project_structure():
    """Ensures the essential project directory structure exists."""
    ensure_dir(VIBE_PROJECT_DIR)
    ensure_dir(LOGS_DIR)
    ensure_dir(COSTS_DIR)
    ensure_dir(VIBE_DATA_DIR)
    ensure_dir(INSTRUCTIONS_DIR)
    ensure_dir(KNOWLEDGE_DIR)
    ensure_dir(PRODUCT_DIR)
    ensure_dir(PRODUCT_BACKLOG_DIR)
    ensure_dir(PRODUCT_IN_PROGRESS_DIR)
    ensure_dir(PRODUCT_HISTORY_DIR)
    ensure_dir(PRODUCT_NEXT_DIR)
    ensure_dir(PLANNING_INBOX_DIR)
    ensure_dir(PLANNING_REJECTED_DIR)

    # Maintain .gitignore
    setup_project_gitignore()


def migrate_to_project_dir():
    """Migrates legacy files from root to the implementation/ directory."""
    legacy_files = [
        "architecture.yaml",
        "architecture-current.yaml",
        "infrastructure.yaml",
        "infrastructure-current.yaml",
        "project-state.json",
        "state.json",
    ]

    for f in legacy_files:
        old_path = pathlib.Path(f)
        if old_path.exists():
            new_path = VIBE_PROJECT_DIR / f
            if f == "project-state.json" or f == "state.json":
                new_path = PROJECT_STATE_FILE

            if not new_path.exists():
                logger.info(f"Migrating {f} to {new_path}")
                shutil.move(old_path, new_path)
            else:
                logger.warning(
                    f"Cannot migrate {f}: {new_path} already exists. Deleting legacy file."
                )
                old_path.unlink()


def get_agent_processes() -> List[Dict[str, Any]]:
    """Lists all active agent-related processes."""
    from .agent import get_agent_processes as _get_agent_processes

    return _get_agent_processes()


def cleanup_stale_processes() -> List[str]:
    """Kills tracked and floating agent processes."""
    from .agent import cleanup_stale_processes as _cleanup_stale_processes

    return _cleanup_stale_processes()


def get_google_api_key() -> Optional[str]:
    """Retrieves the Google API key from environment variables."""
    return os.environ.get("GOOGLE_API_KEY")


def get_cursor_api_key() -> Optional[str]:
    """Retrieves the Cursor API key from environment variables."""
    return os.environ.get("CURSOR_API_KEY")


def set_env_var(key: str, value: str):
    """Sets an environment variable in the .env file and current process."""
    env_file = find_dotenv() or ".env"

    if os.path.exists(env_file):
        content = pathlib.Path(env_file).read_text()
        lines = content.splitlines()
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}")
        pathlib.Path(env_file).write_text("\n".join(lines) + "\n")
    else:
        pathlib.Path(env_file).write_text(f"{key}={value}\n")

    os.environ[key] = value


def save_cursor_api_key(api_key: str):
    """Saves the Cursor API key to the .env file."""
    set_env_var("CURSOR_API_KEY", api_key)


def save_google_api_key(api_key: str):
    """Saves the Google API key to the .env file."""
    set_env_var("GOOGLE_API_KEY", api_key)


def migrate_env_to_config():
    """DEPRECATED: We no longer migrate envs to config.json."""
    pass


def get_vibe_status_report() -> str:
    """Generates a comprehensive status report for the project."""
    import click
    from .cost import get_total_cost
    from .servers import get_container_status, get_server_configs

    state = load_project_state()
    report = []

    # Status report is returned as a string, usually printed by the caller.
    # We should keep it as click.style for terminal, but OutputManager might need to handle rich/click strings.
    # For now, let's keep it as is, but consider if we should convert it to plain text for history.
    report.append(click.style("=== VIBE PROJECT STATUS ===", fg="cyan", bold=True))

    # 1. Project Directory Info
    report.append(click.style("\nPROJECT DIRECTORY:", fg="yellow", bold=True))
    report.append(f"  Location:    {os.getcwd()}")
    report.append(f"  Data Dir:    {VIBE_PROJECT_DIR}")

    # 2. Lifecycle Phases
    report.append(click.style("\nLIFECYCLE PHASES:", fg="yellow", bold=True))
    phases = state.get("phases", {})

    # Map phases to display names and help commands
    phase_meta = {
        "setup": {"name": "Architecture Setup", "cmd": "vibe setup"},
        "implement": {"name": "Implementation", "cmd": "vibe implement"},
        "testing": {"name": "Testing & Recon", "cmd": "vibe testing"},
        "infra": {"name": "Infrastructure", "cmd": "vibe infra"},
        "deploy": {"name": "Deployment", "cmd": "vibe deploy"},
    }

    for phase_id, meta in phase_meta.items():
        phase_data = phases.get(phase_id, {"status": "pending"})
        status = phase_data.get("status", "pending")

        if status == "completed":
            status_display = click.style("✅ DONE", fg="green")
        elif status == "in_progress":
            status_display = click.style("⏳ IN_PROGRESS", fg="blue")
        else:
            status_display = click.style("⚪ PENDING", fg="white", dim=True)

        report.append(f"  - {meta['name']:<20} {status_display:<15} ({meta['cmd']})")

    # 3. PRD Progress
    report.append(click.style("\nPRD PROGRESS:", fg="yellow", bold=True))
    prd_info = collect_all_prd_info()
    completed_prds = state.get("completed_prds", [])
    started_prds = state.get("started_prds", [])

    if not prd_info:
        report.append(
            f"  {click.style('⚪ No PRDs found', fg='white', dim=True)} (Add markdown specs to product/)"
        )
    else:
        done_count = 0
        total_count = len(prd_info)

        from vibe_tools.prds import load_prd

        for info in prd_info:
            name = info["name"]
            prd_stem = info["md_path"].stem

            if prd_stem in completed_prds or name in completed_prds:
                done_count += 1

        # Summary line
        report.append(f"  Overall: {done_count}/{total_count} PRDs implemented")

        # List individual PRDs (latest 5)
        report.append("  Recent PRDs:")
        for info in prd_info[-5:]:
            name = info["name"]
            prd_stem = info["md_path"].stem
            md_path = info["md_path"]

            prd_obj = None
            try:
                prd_obj = load_prd(md_path)
            except Exception:
                pass

            if prd_stem in completed_prds or name in completed_prds:
                status = click.style("✅", fg="green")
                progress_str = ""
            elif (
                prd_stem in started_prds
                or name in started_prds
                or (prd_obj and prd_obj.status == "in_progress")
            ):
                status = click.style("⏳", fg="blue")
                if prd_obj:
                    p_parts = []
                    if prd_obj.impl_code_ready:
                        p_parts.append("C")
                    if prd_obj.impl_tests_passed:
                        p_parts.append("T")
                    if prd_obj.impl_review_passed:
                        p_parts.append("R")
                    progress_str = (
                        f" ({','.join(p_parts)})" if p_parts else " (started)"
                    )
                else:
                    progress_str = " (started)"
            else:
                status = click.style("⚪", fg="white", dim=True)
                progress_str = ""

            report.append(f"    {status} {name}{progress_str}")

    # 4. Implementation Plans
    report.append(click.style("\nIMPLEMENTATION PLANS:", fg="yellow", bold=True))
    all_plans = state.get("plans", {})
    if all_plans:
        for plan_id, plan_info in all_plans.items():
            status = plan_info.get("status", "pending")
            if status == "completed":
                status_display = click.style("✅ DONE", fg="green")
            elif status == "in_progress":
                status_display = click.style("⏳ IN_PROGRESS", fg="blue")
            elif status == "failed":
                status_display = click.style("❌ FAILED", fg="red")
            else:
                status_display = click.style("⚪ PENDING", fg="white", dim=True)

            deps = plan_info.get("depends_on", [])
            dep_str = f" (Needs: {', '.join(deps)})" if deps else ""
            report.append(f"    - {plan_id:<30} {status_display}{dep_str}")
    else:
        report.append(
            f"  {click.style('⚪ No plans found', fg='white', dim=True)} (Run 'vibe setup' to generate plans from PRDs)"
        )

    # 5. Instructions & Prompts
    report.append(click.style("\nINSTRUCTIONS & PROMPTS:", fg="yellow", bold=True))
    if INSTRUCTIONS_DIR.exists():
        instr_files = sorted(list(INSTRUCTIONS_DIR.glob("*")))
        if instr_files:
            report.append("  Instructions:")
            for f in instr_files:
                if f.is_file():
                    report.append(f"    - {f.name}")
        else:
            report.append("  No instructions found.")
    else:
        report.append("  No instructions directory.")

    prompts_dir = pathlib.Path("prompts")
    if prompts_dir.exists():
        prompt_overrides = sorted(list(prompts_dir.glob("*.txt")))
        if prompt_overrides:
            report.append("  Prompt Overrides:")
            for f in prompt_overrides:
                report.append(f"    - {f.name}")
        else:
            report.append("  No prompt overrides found (using system defaults).")
    else:
        report.append("  No prompts directory (using system defaults).")

    # 6. Next Steps
    # next_action logic removed for brevity as it depends on more context
    next_action = None

    if next_action:
        report.append(click.style("\nNEXT SUGGESTED ACTION:", fg="green", bold=True))
        report.append(f"  > {next_action}")

    # 7. Next Branch Info
    report.append(click.style("\nNEXT BRANCH:", fg="yellow", bold=True))

    config = load_config()
    ralph_config = config.get("ralph", {})
    auto_merge = ralph_config.get("auto_merge", False)
    automerge_branch = get_automerge_branch(config)

    if auto_merge:
        report.append(f"  - Automerge: {click.style('ENABLED', fg='green')}")
        report.append(f"  - Target:    {click.style(automerge_branch, fg='cyan')}")
    else:
        report.append(f"  - Automerge: {click.style('DISABLED', fg='white', dim=True)}")

    next_plan_id = None
    if all_plans:
        # Find the first pending plan
        for pid, pinfo in all_plans.items():
            if pinfo.get("status") == "pending":
                next_plan_id = pid
                break

    if next_plan_id:
        plan_info = all_plans[next_plan_id]
        branch = plan_info.get("branch", f"feature/{next_plan_id}")
        parent = plan_info.get("parent_branch", get_main_branch())
        report.append(f"  - Next:   {click.style(branch, fg='cyan')}")
        report.append(f"  - Based Off: {click.style(parent, fg='blue')}")
    else:
        report.append("  - No pending implementation plans found.")

    # 8. Costs
    total_cost = get_total_cost()
    report.append(click.style("\nCOSTS:", fg="yellow", bold=True))
    report.append(
        f"  Total Estimated Project Cost: {click.style(f'${total_cost:.4f} USD', fg='green')}"
    )

    # 9. Services
    report.append(click.style("\nSERVICES:", fg="yellow", bold=True))
    configs = get_server_configs()
    if not configs:
        report.append("  No services configured.")
    else:
        for name, config in configs.items():
            status = get_container_status(config["container_name"])
            if status == "running":
                status_display = click.style("✅ Running", fg="green")
            elif status == "exited":
                status_display = click.style("🛑 Stopped", fg="red")
            else:
                status_display = click.style("⚪ Not Installed", fg="white", dim=True)

            ports = ", ".join([f"{v}" for k, v in config.get("ports", {}).items()])
            report.append(f"  - {name:<15} {status_display:<20} {ports}")

    report.append("")
    return "\n".join(report)


def check_env_health() -> bool:
    """Checks if the current environment is healthy and correctly configured."""
    # 1. Check if project package is importable
    project_name = get_project_name()
    package_found = False

    for pkg in ["backend", project_name, "src"]:
        try:
            if importlib.util.find_spec(pkg):
                logger.debug(f"✅ '{pkg}' package is importable.")
                package_found = True
                break
        except (ImportError, AttributeError, ValueError):
            continue

    if not package_found:
        logger.warning(
            "❌ No project package found (backend, src, or project_name). Project structure may be broken."
        )
        # We don't return False here yet as it might be a fresh project
    else:
        logger.debug("✅ Project package structure verified.")

    return True


def fix_kubeconfig_api_version() -> bool:
    """Checks for deprecated kubeconfig API versions and updates them to v1beta1 if needed."""
    kubeconfig_path = pathlib.Path.home() / ".kube" / "config"
    if not kubeconfig_path.exists():
        return False

    try:
        content = kubeconfig_path.read_text()
        if "client.authentication.k8s.io/v1alpha1" in content:
            new_content = content.replace(
                "client.authentication.k8s.io/v1alpha1",
                "client.authentication.k8s.io/v1beta1",
            )
            kubeconfig_path.write_text(new_content)
            return True
    except Exception as e:
        logger.error(f"Error fix kubeconfig API version: {e}")

    return False


def maybe_init_git():
    """Checks if the current directory is a git repository and offers to initialize it if not."""
    import click

    if not is_git_repo():
        if click.confirm(
            "\nNo git repository found. Would you like to initialize one?", default=True
        ):
            try:
                subprocess.run(["git", "init"], check=True)
                out_success("✅ Initialized empty Git repository.")
            except Exception as e:
                out_error(f"❌ Failed to initialize Git repository: {e}")


def setup_project_gitignore():
    """Sets up the project's .gitignore file with default patterns."""
    patterns = [
        "__pycache__/",
        "*.py[cod]",
        "*$py.class",
        "*.egg-info/",
        ".DS_Store",
        ".cursor/",
        ".venv/",
        "venv/",
        "env/",
        ".env",
        "build/",
        "dist/",
        "prds/",
        ".vite/vitest/results.json",
        ".coverage/",
        "node_modules/",
        "reports/",
        "implementation/costs/",
        "implementation/logs/*",
        "vibe_tools/_version.py",
        "vibe_tools/version.py",
        "*.pyc",
        "*.log",
        ".vibe_config.json",
        "implementation/config.json",
        "implementation/run-pids.json",
        "implementation/logs/",
        "implementation/costs/usage.csv",
        "frontend/src-tauri/target/",
        "frontend/src-tauri/implementation/",
        "frontend/src-tauri/gen/",
        "frontend/src-tauri/tauri-build/",
        "frontend/dist/",
    ]
    ensure_gitignore(patterns)


def save_memory(text: str) -> pathlib.Path:
    """Saves a 'memory' instruction to the instructions directory."""
    ensure_dir(INSTRUCTIONS_DIR)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # slugify text for filename
    slug = "".join(c if c.isalnum() else "_" for c in text[:30]).lower()
    filename = f"memory_{timestamp}_{slug}.txt"
    filepath = INSTRUCTIONS_DIR / filename
    filepath.write_text(text)
    return filepath


def merge_insights(old_memory: str, new_insights: str) -> str:
    """Merges incremental agent insights into the current PRD's operational memory via LLM."""
    if not new_insights:
        return old_memory

    merge_prompt = f"""
Merge the following new insights into the existing short-term memory for this task.
Keep it concise and focused on progress, architectural decisions, and blockers found.

OLD MEMORY:
{old_memory or "None"}

NEW INSIGHTS:
{new_insights}

Output ONLY the updated memory text. No headers, no intro, no tags.
"""
    updated_memory = run_llm(merge_prompt, model="gemini-3-flash")
    return updated_memory.strip() if updated_memory else old_memory


def update_global_knowledge(prd_id: str, insights: str):
    """Uses an LLM to categorize and update global knowledge files."""
    if not insights:
        return

    ensure_dir(KNOWLEDGE_DIR)
    existing_categories = [f.stem for f in KNOWLEDGE_DIR.glob("*.md")]

    update_prompt = f"""
You are a knowledge manager for the Ralph Loop. Based on the following insights from PRD {prd_id}, 
determine which knowledge category (file) should be updated or if a new one is needed.

Existing categories: {', '.join(existing_categories) if existing_categories else "None"}

INSIGHTS:
{insights}

Output your response in the following format:
CATEGORY: <category_name>
CONTENT: <The complete updated content for this category .md file, incorporating the new insights logically into the existing patterns.>

If multiple categories need updates, output them sequentially.
If no category fits and a new one is needed, create a descriptive name.
Output ONLY the categories and content as specified.
"""
    response = run_llm(update_prompt, model="gemini-3-flash")
    if response:
        # Simple parsing logic for the LLM output
        category_matches = re.finditer(
            r"CATEGORY:\s*(.*?)\nCONTENT:\s*(.*?)(?=\nCATEGORY:|$)",
            response,
            re.DOTALL,
        )
        for match in category_matches:
            category = match.group(1).strip()
            content = match.group(2).strip()

            if category and content:
                # Basic slugify for safety
                category_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", category)
                kb_file = KNOWLEDGE_DIR / f"{category_slug}.md"
                kb_file.write_text(content)
                out_success(f"🧠 Updated global knowledge: {kb_file.name}")


def perform_basic_init():
    """Helper to initialize the project structure and essential templates."""
    from vibe_tools.templates import TEMPLATES

    maybe_init_git()

    # First, migrate any existing files from root to implementation/
    migrate_to_project_dir()

    # Migrate environment configuration to config.json
    migrate_env_to_config()

    # Ensure structure exists
    ensure_project_structure()
    ensure_dir(VIBE_PROJECT_DIR)

    # Create config.json if it doesn't exist
    if not CONFIG_FILE.exists():
        default_config = {
            "ralph": {"review": True, "tests": True, "auto_merge": False},
            "default_budget": 5.0,
            "verbose": False,
            "coverage_targets": {
                "backend": 85,
                "frontend": 85,
                "tauri": 85,
                "infra": 85,
            },
            "setup": {"standalone": True},
        }
        CONFIG_FILE.write_text(json.dumps(default_config, indent=2))
        out_success(f"✅ Created default configuration: {CONFIG_FILE}")
    else:
        out_info(f"✅ Configuration already exists: {CONFIG_FILE}")

    # Setup gitignore with specific patterns
    setup_project_gitignore()

    # Create conftest.py if it doesn't exist
    conftest_path = pathlib.Path("tests/conftest.py")
    if not conftest_path.exists():
        ensure_dir(conftest_path.parent)
        conftest_content = """import pytest
import os

# vibe-tools non-intrusive testing policy is enforced automatically via the pytest plugin.
# The following environment variables are set by default:
# VIBE_TEST_MODE=1
# VIBE_AGENT_ACTIVE=1

@pytest.fixture(autouse=True)
def setup_vibe_test_env(monkeypatch):
    # Local project specific test setup
    pass
"""
        conftest_path.write_text(conftest_content)
        out_success(f"✅ Created default test safeguard: {conftest_path}")

    # Create new directories for instructions and specs
    ensure_dir(INSTRUCTIONS_DIR)
    ensure_dir(pathlib.Path("product"))
    ensure_dir(LOGS_DIR)
    ensure_dir(COSTS_DIR)
    ensure_dir(VIBE_DATA_DIR)

    # Only create Makefile if it doesn't exist
    if "Makefile" in TEMPLATES:
        makefile_path = pathlib.Path("Makefile")
        if not makefile_path.exists():
            out_info(f"Creating template: {makefile_path}")
            makefile_path.write_text(TEMPLATES["Makefile"])
        else:
            out_info(f"Template already exists: {makefile_path}")


def get_services():
    """Get services from dev_environment-current.yaml, dev_environment.md, or Makefile."""
    services = []

    # Try dev_environment-current.yaml first (represents the last successful build)
    if DEV_ENV_CURRENT.exists():
        try:
            build_config = safe_yaml_load(DEV_ENV_CURRENT.read_text())
            if build_config:
                services = extract_services_from_build_config(build_config)
                if services:
                    return services
        except Exception:
            pass

    # Try Makefile
    services = extract_services_from_makefile()
    if services:
        return services

    # Try dev_environment.md
    services = extract_services_from_dev_env_md()
    if services:
        return services

    # Fallback: try common commands
    makefile_path = pathlib.Path("Makefile")
    if makefile_path.exists():
        # Just try make dev or make run
        return [
            {
                "name": "development",
                "start_command": "make dev",
            }
        ]

    return []


def test_build_services(debug=False, return_report=False):
    """Test that services defined in build config can actually start and respond.

    Returns:
        If return_report is False: bool (success)
        If return_report is True: (bool, str) (success, detailed_report)
    """

    report = []

    def log_report(msg, level="info"):
        report.append(msg)
        if level == "info":
            logger.info(msg)
        elif level == "debug":
            logger.debug(msg)
        elif level == "warning":
            logger.warning(msg)
        elif level == "error":
            logger.error(msg)

    services = get_services()
    if not services:
        logger.debug("No services found to test")
        log_report("  ⚠️  No services configured to test", "info")
        return (False, "\n".join(report)) if return_report else False

    # Check and fix kubeconfig if skaffold is being used
    if uses_skaffold(services):
        log_report("  🔍 Detected skaffold usage, checking kubeconfig...", "info")
        if fix_kubeconfig_api_version():
            log_report("  ✅ Updated kubeconfig to use v1beta1 API version", "info")
        else:
            logger.debug("Kubeconfig API version check completed (no changes needed)")

    log_report(f"  📋 Found {len(services)} service(s) to test", "info")
    for service in services:
        service_name = service.get("name", "unknown")
        start_cmd = service.get("start_command", "N/A")
        logger.debug(f"Service: {service_name}, Start command: {start_cmd}")

    # Stop any existing services first
    logger.debug("Stopping any existing services before testing")
    try:
        # Call stop logic directly
        services_to_stop = get_services()
        stopped_count = 0
        for service in services_to_stop:
            service_name = service.get("name", "unknown")
            pids = load_pids()
            pid_info = pids.get(service_name, {})

            # Kill background services
            background_services = pid_info.get("background_services", {})
            for service_type, bg_pid in background_services.items():
                try:
                    run_command(["kill", str(bg_pid)], check=False)
                    logger.debug(
                        f"Stopped background service {service_name} ({service_type}) PID: {bg_pid}"
                    )
                except Exception as e:
                    logger.debug(
                        f"Error stopping background service {service_name} ({service_type}) PID {bg_pid}: {e}"
                    )

            # Kill main PID
            main_pid = pid_info.get("main_pid")
            if main_pid:
                try:
                    run_command(["kill", str(main_pid)], check=False)
                    logger.debug(f"Stopped main service {service_name} PID: {main_pid}")
                    stopped_count += 1
                except Exception as e:
                    logger.debug(
                        f"Error stopping main service {service_name} PID {main_pid}: {e}"
                    )

            # Kill child PIDs
            child_pids = pid_info.get("child_pids", [])
            for child_pid in child_pids:
                try:
                    run_command(["kill", str(child_pid)], check=False)
                    logger.debug(
                        f"Stopped child process {service_name} PID: {child_pid}"
                    )
                except Exception as e:
                    logger.debug(
                        f"Error stopping child process {service_name} PID {child_pid}: {e}"
                    )

        save_pids({})
        if stopped_count > 0:
            logger.debug(f"Stopped {stopped_count} existing service(s)")
        time.sleep(1)  # Give services time to stop
    except Exception as e:
        logger.debug(f"Error stopping existing services: {e}", exc_info=True)

    # Try to start services - call start logic directly
    logger.info("  🚀 Starting services for testing...")
    started_processes = []
    try:
        # Use the same logic as the start command but simplified
        for service in services:
            service_name = service.get("name", "unknown")
            start_cmd = service.get("start_command")
            if not start_cmd:
                logger.debug(f"Service {service_name} has no start_command, skipping")
                continue

            import shlex

            cmd_parts = (
                shlex.split(start_cmd) if isinstance(start_cmd, str) else start_cmd
            )

            if not cmd_parts:
                logger.debug(f"Service {service_name}: Empty command parts")
                continue

            logger.debug(
                f"Service {service_name}: Attempting to start with command: {start_cmd}"
            )

            if cmd_parts[0] == "make":
                # For make commands, just run them
                try:
                    process = subprocess.Popen(
                        cmd_parts,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        cwd=service.get("working_directory", "."),
                    )
                    started_processes.append((service_name, process))
                    log_report(
                        f"  ✓ Started {service_name} (PID: {process.pid})", "info"
                    )
                    logger.debug(
                        f"Service {service_name} started with PID {process.pid}, command: {start_cmd}"
                    )
                    time.sleep(0.5)  # Give it a moment
                except Exception as e:
                    log_report(f"  ✗ Failed to start {service_name}: {e}", "warning")
                    logger.debug(
                        f"Service {service_name} startup error: {e}", exc_info=True
                    )
            else:
                # Direct command
                if command_exists(cmd_parts[0]):
                    try:
                        process = subprocess.Popen(
                            cmd_parts,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            cwd=service.get("working_directory", "."),
                        )
                        started_processes.append((service_name, process))
                        log_report(
                            f"  ✓ Started {service_name} (PID: {process.pid})", "info"
                        )
                        logger.debug(
                            f"Service {service_name} started with PID {process.pid}, command: {start_cmd}"
                        )
                        time.sleep(0.5)
                    except Exception as e:
                        log_report(
                            f"  ✗ Failed to start {service_name}: {e}", "warning"
                        )
                        logger.debug(
                            f"Service {service_name} startup error: {e}", exc_info=True
                        )
                else:
                    log_report(
                        f"  ✗ Command not found for {service_name}: {cmd_parts[0]}",
                        "warning",
                    )
                    logger.debug(
                        f"Service {service_name}: Command '{cmd_parts[0]}' does not exist in PATH"
                    )

        # Save PIDs for tracking
        if started_processes:
            tracked_pids = load_pids()
            service_dict = {s.get("name", "unknown"): s for s in services}
            for service_name, process in started_processes:
                if process.poll() is None:  # Still running
                    service_info = service_dict.get(service_name, {})
                    tracked_pids[service_name] = {
                        "main_pid": process.pid,
                        "command": service_info.get("start_command", ""),
                    }
            save_pids(tracked_pids)

        # Wait for services to start
        logger.debug("Waiting 3 seconds for services to start...")
        time.sleep(3)

        # Check for immediate failures in started processes (non-blocking)
        for service_name, process in started_processes:
            if process.poll() is not None:
                # Process has already terminated - skip communicate() to avoid blocking
                exit_code = process.returncode
                log_report(
                    f"  ✗ Service {service_name} exited immediately with code {exit_code}",
                    "warning",
                )

        # Check if services are actually running
        log_report("  🔍 Checking service status...", "info")
        tracked_pids = load_pids()
        running_count = 0
        failed_services = []

        # First check the directly started processes
        for service_name, process in started_processes:
            if process.poll() is None:  # Still running
                is_running = True
                running_count += 1
                log_report(
                    f"  ✓ {service_name} is running - started process (PID: {process.pid})",
                    "info",
                )
                logger.debug(
                    f"Service {service_name} verified running via started process PID {process.pid}"
                )

        # Then check tracked PIDs for services not in started_processes
        for service in services:
            service_name = service.get("name", "unknown")
            # Skip if we already found it running
            if any(name == service_name for name, _ in started_processes):
                continue

            pid_info = tracked_pids.get(service_name, {})
            is_running = False
            running_reason = None

            # Check background services first
            background_services = pid_info.get("background_services", {})
            if background_services:
                logger.debug(
                    f"Service {service_name}: Checking {len(background_services)} background service(s)"
                )

            for service_type, bg_pid in background_services.items():
                try:
                    _, code = run_command(["kill", "-0", str(bg_pid)], check=False)
                    if code == 0:
                        is_running = True
                        running_count += 1
                        running_reason = (
                            f"background service ({service_type}, PID: {bg_pid})"
                        )
                        log_report(
                            f"  ✓ {service_name} is running - {running_reason}", "info"
                        )
                        logger.debug(
                            f"Service {service_name} verified running via background service {service_type} (PID: {bg_pid})"
                        )
                        break
                    else:
                        logger.debug(
                            f"Service {service_name} background service {service_type} (PID: {bg_pid}) is not running (kill -0 returned {code})"
                        )
                except Exception as e:
                    logger.debug(
                        f"Service {service_name} error checking background service {service_type} (PID: {bg_pid}): {e}"
                    )

            # Check main PID if no background services
            if not is_running:
                main_pid = pid_info.get("main_pid")
                if main_pid:
                    try:
                        _, code = run_command(
                            ["kill", "-0", str(main_pid)], check=False
                        )
                        if code == 0:
                            is_running = True
                            running_count += 1
                            running_reason = f"main process (PID: {main_pid})"
                            log_report(
                                f"  ✓ {service_name} is running - {running_reason}",
                                "info",
                            )
                            logger.debug(
                                f"Service {service_name} verified running via main PID {main_pid}"
                            )
                        else:
                            logger.debug(
                                f"Service {service_name} main PID {main_pid} is not running (kill -0 returned {code})"
                            )
                    except Exception as e:
                        logger.debug(
                            f"Service {service_name} error checking main PID {main_pid}: {e}"
                        )
                else:
                    logger.debug(
                        f"Service {service_name}: No main PID found in tracked_pids"
                    )

            # Check by process name if still not found
            if not is_running:
                process_name = pid_info.get("process_name")
                if process_name:
                    try:
                        result = run_command(["pgrep", "-f", process_name], check=False)
                        if result[0].strip():
                            is_running = True
                            running_count += 1
                            running_reason = f"process name match: {process_name}"
                            log_report(
                                f"  ✓ {service_name} is running - {running_reason}",
                                "info",
                            )
                            logger.debug(
                                f"Service {service_name} found running by process name: {process_name}"
                            )
                        else:
                            logger.debug(
                                f"Service {service_name}: No process found matching name '{process_name}'"
                            )
                    except Exception as e:
                        logger.debug(
                            f"Service {service_name} error checking process name '{process_name}': {e}"
                        )
                else:
                    logger.debug(f"Service {service_name}: No process_name configured")

            if not is_running:
                failed_services.append(service_name)
                if not pid_info:
                    log_report(
                        f"  ✗ {service_name} is not running - No PID information found (service may not have started)",
                        "warning",
                    )
                elif not background_services and not main_pid and not process_name:
                    log_report(
                        f"  ✗ {service_name} is not running - No PID tracking data available",
                        "warning",
                    )
                else:
                    log_report(
                        f"  ✗ {service_name} is not running - Process not found",
                        "warning",
                    )

        # Check if URLs are responding
        log_report("  🌐 Checking URL endpoints...", "info")
        urls = extract_urls_from_dev_env()
        if not urls:
            logger.debug("No URLs found in build configuration to check")
        else:
            logger.debug(f"Found {len(urls)} URL(s) to check: {list(urls.keys())}")

        responding_urls = 0
        failed_urls = []
        for url_key, url in urls.items():
            logger.debug(f"Checking URL {url_key}: {url}")
            try:
                if check_url_responds(url):
                    responding_urls += 1
                    log_report(f"  ✓ {url_key} ({url}) is responding", "info")
                    logger.debug(f"URL {url_key} ({url}) responded successfully")
                else:
                    failed_urls.append((url_key, url))
                    log_report(f"  ✗ {url_key} ({url}) is not responding", "warning")
                    logger.debug(
                        f"URL {url_key} ({url}) failed to respond (connection timeout or refused)"
                    )
            except Exception as e:
                failed_urls.append((url_key, url))
                log_report(f"  ✗ {url_key} ({url}) check failed: {e}", "warning")
                logger.debug(f"URL {url_key} ({url}) check error: {e}", exc_info=True)

        # Consider success if at least one service is running or one URL is responding
        success = running_count > 0 or responding_urls > 0

        # Summary logging - always log
        log_report("  📊 Test Summary:", "info")
        log_report(f"     Services: {running_count}/{len(services)} running", "info")
        if failed_services:
            log_report(f"     Failed services: {', '.join(failed_services)}", "info")
        log_report(f"     URLs: {responding_urls}/{len(urls)} responding", "info")
        if failed_urls:
            failed_url_list = [f"{key} ({url})" for key, url in failed_urls]
            log_report(f"     Failed URLs: {', '.join(failed_url_list)}", "info")

        if success:
            log_report(
                "  ✅ Service test PASSED - At least one service or URL is responding",
                "info",
            )
            logger.debug(
                f"Service test passed: {running_count} service(s) running, {responding_urls} URL(s) responding"
            )
        else:
            failure_reasons = []
            if running_count == 0:
                failure_reasons.append(f"no services running (0/{len(services)})")
            if responding_urls == 0 and urls:
                failure_reasons.append(f"no URLs responding (0/{len(urls)})")
            elif not urls and running_count == 0:
                failure_reasons.append("no services running and no URLs configured")
            reason = "; ".join(failure_reasons) if failure_reasons else "unknown"
            log_report(f"  ✗ Service test FAILED - {reason}", "warning")
            logger.debug(
                f"Service test failed: {running_count} service(s) running, {responding_urls} URL(s) responding"
            )

        return (success, "\n".join(report)) if return_report else success

    except Exception as e:
        log_report(f"  ❌ Error testing services: {e}", "error")
        logger.debug(f"Service test exception: {e}", exc_info=True)
        return (False, "\n".join(report)) if return_report else False


def command_exists(cmd):
    """Check if a command exists in PATH."""
    import shutil

    return shutil.which(cmd) is not None


def is_tool_available(tool: str) -> bool:
    """Checks if a tool is available in the system PATH."""
    import shutil

    return shutil.which(tool) is not None


def get_project_root() -> pathlib.Path:
    """Returns the project root directory, either from the global registry or current git repo."""
    # 1. Check global registry
    project = GlobalProjectRegistry.get_project_by_path(str(pathlib.Path.cwd()))
    if project:
        return pathlib.Path(project["path"])

    # 2. Fallback to git root
    try:
        curr = pathlib.Path.cwd()
        for parent in [curr] + list(curr.parents):
            if (parent / ".git").exists():
                return parent
    except Exception:
        pass

    # 3. Default to CWD
    return pathlib.Path.cwd()


def get_project_name() -> str:
    """Returns the project name based on the current directory or git remote."""
    if is_git_repo():
        stdout, code = run_command(["git", "remote", "get-url", "origin"], check=False)
        if code == 0 and stdout.strip():
            url = stdout.strip()
            if url.endswith(".git"):
                url = url[:-4]
            return url.split("/")[-1].split(":")[-1].lower().replace("-", "_")
    return pathlib.Path.cwd().name.lower().replace("-", "_")


def save_google_api_key(api_key: str):
    """Saves the Google API key to the .env file."""
    env_file = find_dotenv() or ".env"
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            f.write("")
    set_key(env_file, "GOOGLE_API_KEY", api_key)


def sync_env_file():
    """DEPRECATED: We no longer sync project config to .env."""
    pass


def get_instructions_context():
    """Reads all files in INSTRUCTIONS_DIR and returns them as a formatted string."""
    if not INSTRUCTIONS_DIR.exists():
        return ""

    sections = []
    for f in sorted(INSTRUCTIONS_DIR.glob("*")):
        if f.is_file():
            content = f.read_text().strip()
            if content:
                sections.append(f"--- {f.name} ---\n{content}")

    if not sections:
        return ""

    return "INSTRUCTIONS:\n" + "\n\n".join(sections)


def get_knowledge_context() -> str:
    """Reads all markdown files in KNOWLEDGE_DIR and returns their summary/links."""
    if not KNOWLEDGE_DIR.exists():
        return ""

    knowledge_files = sorted(list(KNOWLEDGE_DIR.glob("*.md")))
    if not knowledge_files:
        return ""

    context = "GLOBAL KNOWLEDGE BASE:\n"
    context += "The following knowledge categories are available. Reference them if needed:\n"
    for f in knowledge_files:
        # Include just the filename/category and a preview or instruction to read it
        context += f"- {f.name}: (Use 'read_file' on this path if you need details on this category)\n"

    return context + "\n"


def is_merged(branch_name):
    """Checks if a branch is merged into main."""
    _, code = run_command(
        ["git", "merge-base", "--is-ancestor", branch_name, "main"], check=False
    )
    return code == 0


def get_changed_files(base_branch="main"):
    """Returns files changed relative to the base branch."""
    if not is_git_repo():
        return []

    stdout, code = run_command(["git", "merge-base", base_branch, "HEAD"], check=False)
    if code != 0:
        merge_base = base_branch
    else:
        merge_base = stdout.strip() or base_branch

    stdout, code = run_command(["git", "diff", "--name-only", merge_base], check=False)
    if code != 0:
        changed = []
    else:
        changed = stdout.strip().splitlines() if stdout.strip() else []

    stdout, code = run_command(
        ["git", "ls-files", "--others", "--exclude-standard"], check=False
    )
    if code == 0 and stdout.strip():
        changed.extend(stdout.strip().splitlines())

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for path in changed:
        if path and path not in seen:
            seen.add(path)
            unique.append(path)

    return unique


def is_dirty():
    """Checks if the repository has uncommitted changes or untracked files."""
    if not is_git_repo():
        return False
    # Check for tracked changes
    _, code = run_command(["git", "diff", "--quiet"], check=False)
    if code != 0:
        return True
    _, code = run_command(["git", "diff", "--cached", "--quiet"], check=False)
    if code != 0:
        return True
    # Check for untracked files
    stdout, code = run_command(
        ["git", "ls-files", "--others", "--exclude-standard"], check=False
    )
    return bool(stdout.strip())


def load_global_servers() -> Dict[str, Any]:
    """Loads server definitions from the global servers file."""
    if GLOBAL_SERVERS_FILE.exists():
        try:
            return json.loads(GLOBAL_SERVERS_FILE.read_text())
        except Exception as e:
            logger.error(f"Error loading global servers: {e}")
    return {}


def save_global_servers(servers: Dict[str, Any]):
    """Saves server definitions to the global servers file."""
    GLOBAL_SERVERS_FILE.write_text(json.dumps(servers, indent=2))


def check_plan_dependencies(plan_id, all_plans):
    """Placeholder for checking plan dependencies."""
    return []


def commit_and_register_phase(phase_id, project_name=None):
    """Placeholder for committing and registering a phase."""
    pass


def is_phase_completed(phase_id, project_name=None):
    """Placeholder for checking if a phase is completed."""
    return False


def log_issue(tag, *args):
    """Placeholder for logging an issue."""
    message = " ".join(str(a) for a in args)
    out_error(f"ISSUE: [{tag}] {message}", source="vibe")


def log_start(tag, *args):
    """Placeholder for logging the start of an action."""
    message = " ".join(str(a) for a in args)
    if message:
        out_info(f"START: [{tag}] {message}", source="vibe")
    else:
        out_info(f"START: {tag}", source="vibe")


def log_success(tag, *args):
    """Placeholder for logging the success of an action."""
    message = " ".join(str(a) for a in args)
    if message:
        out_success(f"SUCCESS: [{tag}] {message}", source="vibe")
    else:
        out_success(f"SUCCESS: {tag}", source="vibe")


verbose_logger = None


def run_llm(prompt, model="gemini-3-flash", debug=False):
    """Runs an LLM call using the google-genai library."""
    try:
        from google import genai

        api_key = get_google_api_key()
        if not api_key:
            logger.error("GOOGLE_API_KEY not found. Please run `vibe config api`.")
            return None

        # Map aliases
        if model == "gemini-3-flash":
            model = "gemini-2.0-flash-exp"

        client = genai.Client(api_key=api_key)

        if debug:
            out_debug(f"\n--- DEBUG: LLM PROMPT ({model}) ---", source="llm")
            out_debug(prompt, source="llm")
            out_debug("--- END DEBUG ---\n", source="llm")

        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )

        log_large_output(f"llm_prompt_{model}", prompt)
        log_large_output(f"llm_response_{model}", response.text)

        if debug:
            out_debug("\n--- DEBUG: LLM RESPONSE ---", source="llm")
            out_debug(response.text, source="llm")
            out_debug("--- END DEBUG ---\n", source="llm")

        return response.text
    except Exception as e:
        logger.error(f"Error in run_llm: {e}")
        return None


def switch_to_main():
    """Placeholder for switching to the main branch."""
    pass


def update_state_phase(phase_id, status, project_name=None):
    """Placeholder for updating the state phase."""
    pass


def parse_prd_filename(filename):
    """Placeholder for parsing a PRD filename."""
    return {"name": filename}


def open_in_editor(path):
    """Placeholder for opening a file in the editor."""
    pass


def is_port_available(port):
    """Check if a port is available."""
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(("localhost", port))
            return result != 0  # Port is available if connection fails
    except Exception:
        return False


def find_available_port(start_port, max_attempts=10):
    """Find an available port starting from start_port."""
    for i in range(max_attempts):
        port = start_port + i
        if is_port_available(port):
            return port
    return None


def extract_port_from_command(cmd):
    """Extract port number from a command string."""

    # Look for --port, -p, PORT=, or :port patterns
    patterns = [
        r"--port\s+(\d+)",
        r"-p\s+(\d+)",
        r"PORT[=:]\s*(\d+)",
        r":(\d{4,5})",
        r"port\s*=\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, cmd, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def replace_port_in_command(cmd, old_port, new_port):
    """Replace port in a command string."""

    # Replace various port patterns
    cmd = re.sub(
        rf"--port\s+{old_port}", f"--port {new_port}", cmd, flags=re.IGNORECASE
    )
    cmd = re.sub(rf"-p\s+{old_port}", f"-p {new_port}", cmd, flags=re.IGNORECASE)
    cmd = re.sub(
        rf"PORT[=:]\s*{old_port}", f"PORT={new_port}", cmd, flags=re.IGNORECASE
    )
    cmd = re.sub(rf":{old_port}", f":{new_port}", cmd)
    cmd = re.sub(
        rf"port\s*=\s*{old_port}", f"port={new_port}", cmd, flags=re.IGNORECASE
    )
    return cmd


def extract_services_from_build_config(build_config):
    """Extract services from dev_environment.yaml config."""
    services = build_config.get("services", [])
    if services:
        return services
    return []


def parse_makefile_target(target_name, makefile_content, visited=None):
    """Parse a Makefile target to extract the commands it runs."""

    if visited is None:
        visited = set()

    # Prevent infinite recursion
    if target_name in visited:
        return []
    visited.add(target_name)

    # Find the target definition - match until next target or end of file
    target_pattern = rf"^{target_name}:\s*(.*?)(?=^[a-zA-Z_][a-zA-Z0-9_-]*:|^$)"
    match = re.search(target_pattern, makefile_content, re.MULTILINE | re.DOTALL)
    if not match:
        return []

    target_content = match.group(1)
    commands = []

    # Extract commands (lines starting with tab)
    for line in target_content.splitlines():
        # Check if line starts with tab (actual command) or @ (silent command)
        if not (line.startswith("\t") or line.startswith("\t@")):
            continue

        # Remove leading tab and @
        line = line.lstrip("\t@").strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        # Skip echo commands (but keep them for debugging)
        if line.startswith("echo"):
            continue

        # Handle make calls to other targets - recursively parse
        if line.startswith("make ") or line.startswith("$(MAKE)"):
            parts = line.split()
            if len(parts) > 1:
                called_target = parts[1]
                # Recursively get commands from called target
                sub_commands = parse_makefile_target(
                    called_target, makefile_content, visited.copy()
                )
                commands.extend(sub_commands)
            continue

        # This is an actual command to run
        if line:
            commands.append(line)

    return commands


def extract_services_from_makefile():
    """Extract services by checking Makefile for dev-related targets."""
    makefile_path = pathlib.Path("Makefile")
    if not makefile_path.exists():
        return []

    services = []
    makefile_content = makefile_path.read_text()

    # Check for common dev start targets (in priority order)
    dev_targets = [
        ("dev-start", "make dev-start", "development"),
        ("dev", "make dev", "development"),
        ("run", "make run", "application"),
        ("start", "make start", "application"),
        ("up", "make up", "services"),
    ]

    found_main_target = False
    for target, cmd, service_name in dev_targets:
        if f"{target}:" in makefile_content or f".PHONY: {target}" in makefile_content:
            # Parse the target to see what it actually does
            target_commands = parse_makefile_target(target, makefile_content)

            # If target just calls other targets or is just echo, try to extract real services
            if not target_commands or all(
                c.startswith("@echo") or c.startswith("echo") for c in target_commands
            ):
                # Try to find backend and frontend targets
                backend_commands = parse_makefile_target(
                    "backend-run", makefile_content
                ) or parse_makefile_target("run", makefile_content)
                frontend_commands = parse_makefile_target(
                    "frontend-run", makefile_content
                ) or parse_makefile_target("frontend-dev", makefile_content)

                if backend_commands:
                    services.append(
                        {
                            "name": "backend",
                            "start_command": (
                                backend_commands[0] if backend_commands else None
                            ),
                            "make_target": (
                                "backend-run"
                                if "backend-run:" in makefile_content
                                else "run"
                            ),
                        }
                    )
                if frontend_commands:
                    services.append(
                        {
                            "name": "frontend",
                            "start_command": (
                                frontend_commands[0] if frontend_commands else None
                            ),
                            "make_target": (
                                "frontend-run"
                                if "frontend-run:" in makefile_content
                                else "frontend-dev"
                            ),
                        }
                    )

                # If we found individual services, use those instead
                if backend_commands or frontend_commands:
                    found_main_target = True
                    break

            # If target has actual commands, use it as-is
            services.append(
                {
                    "name": service_name,
                    "start_command": cmd,
                    "stop_command": (
                        "make dev-stop" if "dev-stop:" in makefile_content else None
                    ),
                }
            )
            found_main_target = True
            break  # Use the first found

    # Check for Skaffold (only if skaffold is installed and config exists)
    if pathlib.Path("skaffold.yaml").exists() and command_exists("skaffold"):
        services.append(
            {
                "name": "skaffold-dev",
                "start_command": "skaffold dev",
                "stop_command": "pkill -f skaffold",
            }
        )

    # Check for backend and frontend separately (only if main target not found)
    if not found_main_target:
        if "frontend-run:" in makefile_content or "frontend-dev:" in makefile_content:
            cmd = (
                "make frontend-run"
                if "frontend-run:" in makefile_content
                else "make frontend-dev"
            )
            services.append(
                {
                    "name": "frontend",
                    "start_command": cmd,
                }
            )
        if "run:" in makefile_content or "backend-run:" in makefile_content:
            cmd = (
                "make backend-run" if "backend-run:" in makefile_content else "make run"
            )
            services.append(
                {
                    "name": "backend",
                    "start_command": cmd,
                }
            )

    return services


def check_url_responds(url):
    """Check if a URL actually responds."""
    try:
        import socket
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port
        if not port:
            # Try to extract from netloc
            if ":" in parsed.netloc:
                port = int(parsed.netloc.split(":")[-1])
            else:
                return False

        # Quick socket check
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def extract_urls_from_dev_env():
    """Extract URLs from dev_environment-current.yaml, dev_environment.md, or Makefile."""
    urls = {}

    # Try dev_environment-current.yaml first
    if DEV_ENV_CURRENT.exists():
        try:
            build_config = safe_yaml_load(DEV_ENV_CURRENT.read_text())
            if build_config:
                # Look for URLs in config
                if "urls" in build_config:
                    for key, url in build_config["urls"].items():
                        # Clean URL (remove markdown links)
                        clean_url = url.split("](")[0] if "](" in url else url
                        clean_url = clean_url.strip("[]()")
                        urls[key] = clean_url
                # Look for services with URLs
                services = build_config.get("services", [])
                for service in services:
                    if "url" in service:
                        url = service["url"]
                        # Clean URL (remove markdown links)
                        clean_url = url.split("](")[0] if "](" in url else url
                        clean_url = clean_url.strip("[]()")
                        urls[service.get("name", "unknown")] = clean_url
        except Exception:
            pass

    # Try dev_environment.md
    if DEV_SPEC.exists():
        build_md = DEV_SPEC.read_text()
        import re

        # Common port patterns
        port_patterns = {
            r"8000": "backend",
            r"3000": "frontend",
            r"5173": "frontend",  # Vite
            r"8080": "backend",
            r"5000": "backend",
        }

        for pattern, service_type in port_patterns.items():
            matches = re.findall(
                rf"localhost:{pattern}|port\s+{pattern}|:{pattern}",
                build_md,
                re.IGNORECASE,
            )
            if matches:
                port = pattern
                if service_type not in urls:
                    urls[service_type] = f"http://localhost:{port}"

        # Look for explicit URL mentions (clean markdown links)
        explicit_urls = re.findall(
            r"\[([^\]]+)\]\(([^\)]+)\)|(https?://[^\s\)\]]+)", build_md
        )
        for match in explicit_urls:
            # Handle markdown link format [text](url) or plain url
            if match[2]:  # Plain URL
                url = match[2]
            elif match[1]:  # URL from markdown link
                url = match[1]
            else:
                continue

            if "localhost" in url or "127.0.0.1" in url:
                # Clean URL
                url = url.split("](")[0] if "](" in url else url
                url = url.strip("[]()")
                if "backend" in url.lower() or "api" in url.lower() or ":8000" in url:
                    urls["backend"] = url
                elif "frontend" in url.lower() or ":3000" in url or ":5173" in url:
                    urls["frontend"] = url

    # Try Makefile for port information
    makefile_path = pathlib.Path("Makefile")
    if makefile_path.exists():
        makefile_content = makefile_path.read_text()
        import re

        # Look for port assignments
        port_matches = re.findall(
            r"(?:PORT|port)\s*[=:]\s*(\d{4,5})", makefile_content, re.IGNORECASE
        )
        for port in port_matches:
            if port == "8000" and "backend" not in urls:
                urls["backend"] = f"http://localhost:{port}"
            elif port in ["3000", "5173"] and "frontend" not in urls:
                urls["frontend"] = f"http://localhost:{port}"

        # Look for uvicorn or runserver commands with ports
        uvicorn_match = re.search(
            r"uvicorn.*?--port\s+(\d+)", makefile_content, re.IGNORECASE
        )
        if uvicorn_match:
            port = uvicorn_match.group(1)
            urls["backend"] = f"http://localhost:{port}"
            urls["api_docs"] = f"http://localhost:{port}/docs"

    return urls


def extract_services_from_dev_env_md():
    """Extract services from dev_environment.md by parsing startup commands."""
    if not DEV_SPEC.exists():
        return []

    services = []
    build_md = DEV_SPEC.read_text()

    # Look for startup commands section

    # Pattern to find commands like "make run", "make dev", "npm run dev", etc.
    startup_patterns = [
        r"`?make\s+(?:dev|run|start|up|dev-start)`?",
        r"`?npm\s+run\s+dev`?",
        r"`?python\s+manage\.py\s+runserver`?",
        r"`?uvicorn\s+.*`?",
        r"`?skaffold\s+dev`?",
    ]

    found_commands = set()
    for pattern in startup_patterns:
        matches = re.findall(pattern, build_md, re.IGNORECASE)
        for match in matches:
            cmd = match.strip("`").strip()
            if cmd and cmd not in found_commands:
                found_commands.add(cmd)
                service_name = cmd.split()[-1] if len(cmd.split()) > 1 else "service"
                services.append(
                    {
                        "name": service_name.replace("-", "_"),
                        "start_command": cmd,
                    }
                )

    return services


def get_pid_file():
    """Get path to PID tracking file."""
    return VIBE_PROJECT_DIR / "run-pids.json"


def load_pids():
    """Load tracked PIDs from file."""
    pid_file = get_pid_file()
    if pid_file.exists():
        try:
            return json.loads(pid_file.read_text())
        except Exception:
            return {}
    return {}


def save_pids(pids):
    """Save tracked PIDs to file."""
    pid_file = get_pid_file()
    ensure_dir(pid_file.parent)
    pid_file.write_text(json.dumps(pids, indent=2))


def uses_skaffold(services: List[Dict[str, Any]]) -> bool:
    """Check if any service in the services list uses skaffold."""
    for service in services:
        start_command = service.get("start_command", "")
        if start_command and "skaffold" in start_command.lower():
            return True
    return False


def check_and_install_build_tools():
    """Check for required build tools (skaffold, helm) and install if missing."""
    import platform

    required_tools = {}

    # Check if skaffold.yaml exists
    skaffold_yaml = pathlib.Path("skaffold.yaml")
    if skaffold_yaml.exists():
        required_tools["skaffold"] = {
            "check_cmd": ["skaffold", "version"],
            "install_cmd_brew": ["brew", "install", "skaffold"],
            "install_cmd_linux": [
                "curl",
                "-Lo",
                "skaffold",
                "https://storage.googleapis.com/skaffold/releases/latest/skaffold-linux-amd64",
                "&&",
                "sudo",
                "install",
                "skaffold",
                "/usr/local/bin/",
            ],
            "description": "Skaffold (Kubernetes development tool)",
        }

    # Check if helm charts exist
    helm_paths = [
        pathlib.Path("deployment/helm"),
        pathlib.Path("helm"),
        pathlib.Path("charts"),
    ]
    has_helm = any(p.exists() for p in helm_paths)

    if has_helm:
        required_tools["helm"] = {
            "check_cmd": ["helm", "version"],
            "install_cmd_brew": ["brew", "install", "helm"],
            "install_cmd_linux": [
                "curl",
                "https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3",
                "|",
                "bash",
            ],
            "description": "Helm (Kubernetes package manager)",
        }

    if not required_tools:
        return

    out_info("🔍 Checking for required build tools...")

    for tool_name, tool_info in required_tools.items():
        # Check if tool is installed
        try:
            result = run_command(tool_info["check_cmd"], check=False)
            if result[1] == 0:
                out_success(f"  ✅ {tool_info['description']} is installed")
                continue
        except Exception:
            pass

        # Tool is not installed
        out_warn(f"  ⚠️  {tool_info['description']} is not installed")

        # Determine OS and install method
        system = platform.system().lower()
        is_macos = system == "darwin"

        if is_macos:
            # Try brew first
            if shutil.which("brew"):
                out_info(f"  📦 Installing {tool_name} using Homebrew...")
                try:
                    install_cmd = tool_info["install_cmd_brew"]
                    result = run_command(install_cmd, check=False)
                    if result[1] == 0:
                        out_success(f"  ✅ {tool_name} installed successfully")
                        continue
                    else:
                        out_warn(f"  ⚠️  Homebrew installation failed: {result[0]}")
                except Exception as e:
                    out_error(f"  ⚠️  Installation error: {e}")
            else:
                out_info(f"  💡 Install {tool_name} manually:")
                out_info(f"     brew install {tool_name}")
        else:
            # Linux - provide manual instructions
            out_info(f"  💡 Install {tool_name} manually:")
            if tool_name == "skaffold":
                out_info(
                    "     curl -Lo skaffold https://storage.googleapis.com/skaffold/releases/latest/skaffold-linux-amd64"
                )
                out_info("     sudo install skaffold /usr/local/bin/")
            elif tool_name == "helm":
                out_info(
                    "     curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"
                )

        # Verify installation
        out_info(f"  🔍 Verifying {tool_name} installation...")
        try:
            result = run_command(tool_info["check_cmd"], check=False)
            if result[1] == 0:
                out_success(f"  ✅ {tool_name} is now available")
            else:
                out_warn(f"  ⚠️  {tool_name} installation verification failed")
                out_info("     Please install it manually and run 'vibe build' again")
        except Exception:
            out_error(f"  ⚠️  Could not verify {tool_name} installation")

    # If skaffold is detected, check and fix kubeconfig API version
    if "skaffold" in required_tools:
        out_info("🔍 Checking kubeconfig for deprecated API versions...")
        if fix_kubeconfig_api_version():
            out_success("  ✅ Updated kubeconfig to use v1beta1 API version")
        else:
            logger.debug("Kubeconfig API version check completed (no changes needed)")
