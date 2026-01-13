import atexit
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
import signal
import subprocess
import sys
import time
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional, Tuple

import yaml
from dotenv import find_dotenv, load_dotenv, set_key

from vibe_tools.command_output import (
    out_debug,
    out_error,
    out_info,
    out_print,
    out_success,
    out_warn,
)

VIBE_PROJECT_DIR = pathlib.Path("implementation")
PRODUCT_DIR = pathlib.Path("product")
PLANNING_DIR = PRODUCT_DIR

# Legacy - to be removed after migration
ISSUES_DIR = pathlib.Path("issues")
ISSUES_BACKLOG_DIR = ISSUES_DIR / "backlog"
ISSUES_HISTORY_DIR = ISSUES_DIR / "history"
ISSUES_FAILS_DIR = ISSUES_DIR / "fails"
ISSUES_META_DIR = ISSUES_DIR / "meta"

# Implementation PRDs (YAML)
PRD_DIR = VIBE_PROJECT_DIR / "prds"
PRD_PROCESSING_DIR = PRD_DIR / "processing"
PRD_DONE_DIR = PRD_DIR / "done"
PRD_FAILED_DIR = PRD_DIR / "failed"

# Legacy implementation dirs
BACKLOG_DIR = PRD_DIR / "backlog"
HISTORY_DIR = PRD_DIR / "history"
REJECTED_DIR = PRD_DIR / "rejected"
INBOX_DIR = PRD_DIR / "inbox"

# Product Planning (Markdown)
PRODUCT_BACKLOG_DIR = PRODUCT_DIR / "backlog"
PRODUCT_IN_PROGRESS_DIR = PRODUCT_DIR / "in_progress"
PRODUCT_HISTORY_DIR = PRODUCT_DIR / "history"
PLANNING_INBOX_DIR = PLANNING_DIR / "inbox"
PLANNING_BACKLOG_DIR = PRODUCT_BACKLOG_DIR
PLANNING_HISTORY_DIR = PRODUCT_HISTORY_DIR
PLANNING_REJECTED_DIR = PLANNING_DIR / "rejected"

PROJECT_STATE_FILE = VIBE_PROJECT_DIR / "state.json"
STATE_FILE = VIBE_PROJECT_DIR / "legacy-state.json"
LOGS_DIR = VIBE_PROJECT_DIR / "logs"
COSTS_DIR = VIBE_PROJECT_DIR / "costs"
INSTRUCTIONS_DIR = VIBE_PROJECT_DIR / "instructions"
VIBE_DATA_DIR = VIBE_PROJECT_DIR / "data"
CONFIG_FILE = VIBE_PROJECT_DIR / "config.json"
GLOBAL_VIBE_DIR = pathlib.Path.home() / ".vibe"

# Core lifecycle files
ARCHITECTURE = VIBE_PROJECT_DIR / "architecture.yaml"
ARCHITECTURE_CURRENT = VIBE_PROJECT_DIR / "architecture-current.yaml"
ARCHITECTURE_SPEC = PLANNING_DIR / "architecture.md"
OVERVIEW = VIBE_PROJECT_DIR / "project_overview.yaml"
OVERVIEW_SPEC = PLANNING_DIR / "project_overview.md"
INFRA = VIBE_PROJECT_DIR / "infrastructure.yaml"
INFRA_CURRENT = VIBE_PROJECT_DIR / "infrastructure-current.yaml"
INFRA_SPEC = PLANNING_DIR / "infrastructure.md"
CICD = VIBE_PROJECT_DIR / "cicd.yaml"
CICD_CURRENT = VIBE_PROJECT_DIR / "cicd-current.yaml"
CICD_SPEC = PLANNING_DIR / "cicd.md"
TESTING_CONFIG = VIBE_PROJECT_DIR / "testing.yaml"
TESTING_CURRENT = VIBE_PROJECT_DIR / "testing-current.yaml"
TESTING_SPEC = PLANNING_DIR / "testing.md"
DEV_ENV = VIBE_PROJECT_DIR / "dev_environment.yaml"
DEV_ENV_CURRENT = VIBE_PROJECT_DIR / "dev_environment-current.yaml"
DEV_SPEC = PLANNING_DIR / "dev_environment.md"
SETUP_SPEC = PLANNING_DIR / "setup.md"

SYSTEM_FILES = [
    "architecture",
    "project_overview",
    "infrastructure",
    "cicd",
    "testing",
    "build",
    "dev_environment",
]
GLOBAL_CONFIG_FILE = GLOBAL_VIBE_DIR / "config.json"
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

    logger.info(f"EVENT: {event_name} -> See {rel_path}")

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
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=check,
        )
        if len(result.stdout.splitlines()) > 5:
            log_large_output(f"command_{command[0]}", result.stdout)
        return result.stdout, result.returncode
    except subprocess.CalledProcessError as e:
        output = (e.stdout or "") + (e.stderr or "")
        if len(output.splitlines()) > 5:
            log_large_output(f"command_{command[0]}_error", output)
        return output, e.returncode
    except (FileNotFoundError, OSError) as e:
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
            return json.loads(target.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_config(config: Dict[str, Any], global_scope: bool = False):
    """Saves the project or global configuration."""
    target = GLOBAL_CONFIG_FILE if global_scope else CONFIG_FILE
    ensure_dir(target.parent)
    target.write_text(json.dumps(config, indent=2))


def load_project_state() -> Dict[str, Any]:
    """Loads the current project state from state.json."""
    if PROJECT_STATE_FILE.exists():
        try:
            return json.loads(PROJECT_STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass

    # Fallback/Default state
    return {
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


def save_project_state(state: Dict[str, Any]):
    """Saves the current project state to state.json."""
    ensure_dir(VIBE_PROJECT_DIR)
    PROJECT_STATE_FILE.write_text(json.dumps(state, indent=2))


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


def setup_logging(command_name: str):
    """Configures logging for a CLI command."""
    global stream_handler, file_handler, LOG_SESSION_DIR
    ensure_dir(LOGS_DIR)

    # Add datetime prefix to log filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"{timestamp}_{command_name}.log"

    # Set the directory for multi-row outputs
    LOG_SESSION_DIR = LOGS_DIR / f"{timestamp}_{command_name}"

    # Root logger configuration
    logger = logging.getLogger("vibe_tools")
    logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers if setup_logging is called multiple times
    if logger.handlers:
        return logger

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

    # Console handler (default to INFO)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(message)s")
    stream_handler.setFormatter(console_formatter)
    logger.addHandler(stream_handler)

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
        import importlib.resources as pkg_resources
        from . import prompts

        return pkg_resources.read_text(prompts, filename)
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


def collect_prd_files() -> List[pathlib.Path]:
    """Collects all machine-readable PRD YAML files."""
    if not PRD_DIR.exists():
        return []
    return sorted(list(PRD_DIR.glob("*.yaml")))


def reset_prd_state(project_name: str) -> List[str]:
    """Resets the state of a PRD, allowing it to be rerun."""
    messages = []
    state = load_project_state()

    # 1. Remove from completed/started lists
    if project_name in state.get("completed_prds", []):
        state["completed_prds"].remove(project_name)
        messages.append(f"Removed '{project_name}' from completed PRDs.")
    if project_name in state.get("started_prds", []):
        state["started_prds"].remove(project_name)
        messages.append(f"Removed '{project_name}' from started PRDs.")

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
            # Also try to delete remote branch if tracking is set up (optional/safe)

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


def ensure_project_structure():
    """Ensures the essential project directory structure exists."""
    ensure_dir(VIBE_PROJECT_DIR)
    ensure_dir(PRD_DIR)
    ensure_dir(LOGS_DIR)
    ensure_dir(COSTS_DIR)
    ensure_dir(VIBE_DATA_DIR)
    ensure_dir(INSTRUCTIONS_DIR)
    ensure_dir(PRODUCT_DIR)
    ensure_dir(PRODUCT_BACKLOG_DIR)
    ensure_dir(PRODUCT_IN_PROGRESS_DIR)
    ensure_dir(PRODUCT_HISTORY_DIR)
    ensure_dir(PLANNING_INBOX_DIR)
    ensure_dir(PLANNING_REJECTED_DIR)


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


def collect_all_prd_info() -> List[Dict[str, Any]]:
    """Collects status information for all PRDs (Markdown and YAML)."""
    prds = {}

    # 1. Look for human specs in product/
    if PLANNING_DIR.exists():
        for f in PLANNING_DIR.rglob("*.md"):
            name = f.stem
            if name in [
                "architecture",
                "infrastructure",
                "cicd",
                "testing",
                "dev_environment",
                "project-overview",
                "project_overview",
            ]:
                continue
            prds[name] = {
                "name": name,
                "has_md": True,
                "md_path": f,
                "has_yaml": False,
                "yaml_path": None,
            }

    # 2. Look for machine specs in implementation/prds/
    if PRD_DIR.exists():
        for f in PRD_DIR.rglob("*.yaml"):
            # Strip 'prd_' prefix if it exists to match with human spec name
            name = f.stem
            clean_name = name
            if name.startswith("prd_"):
                clean_name = name[4:]
            
            # Also handle vXX-XXX_ prefix
            match = re.search(r"v\d+-\d+_(.+)", clean_name)
            if match:
                clean_name = match.group(1)

            if clean_name in prds:
                prds[clean_name]["has_yaml"] = True
                prds[clean_name]["yaml_path"] = f
            else:
                prds[clean_name] = {
                    "name": clean_name,
                    "has_md": False,
                    "md_path": None,
                    "has_yaml": True,
                    "yaml_path": f,
                }

    return sorted(list(prds.values()), key=lambda x: x["name"])


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

        for info in prd_info:
            name = info["name"]
            prd_stem = (
                info["yaml_path"].stem if info["has_yaml"] else info["md_path"].stem
            )

            if prd_stem in completed_prds or name in completed_prds:
                done_count += 1

        # Summary line
        report.append(f"  Overall: {done_count}/{total_count} PRDs implemented")

        # List individual PRDs (latest 5)
        report.append("  Recent PRDs:")
        for info in prd_info[-5:]:
            name = info["name"]
            prd_stem = (
                info["yaml_path"].stem if info["has_yaml"] else info["md_path"].stem
            )

            if prd_stem in completed_prds or name in completed_prds:
                status = click.style("✅", fg="green")
            elif prd_stem in started_prds or name in started_prds:
                status = click.style("⏳", fg="blue")
            else:
                status = click.style("⚪", fg="white", dim=True)

            yaml_icon = "Y" if info["has_yaml"] else " "
            report.append(f"    {status} [{yaml_icon}] {name}")

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
    config = load_config()
    env_config = config.get("env")

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

    # 2. If managed env is configured, check if we're in it
    if env_config:
        venv_name = env_config.get("venv_name")
        if venv_name:
            current_prefix = sys.prefix
            if venv_name not in current_prefix:
                logger.warning(
                    f"⚠️  Managed environment '{venv_name}' is configured but not active."
                )
                logger.warning(f"   Current environment: {current_prefix}")
                return False
            logger.debug(f"✅ Running in managed environment: {venv_name}")

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
        "*.pyc",
        "__pycache__/",
        "*.log",
        ".env",
        ".vibe_config.json",
        "implementation/run-pids.json",
        "implementation/logs/",
        "implementation/costs/usage.csv",
        "node_modules/",
        "dist/",
        "build/",
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


def perform_basic_init():
    """Helper to initialize the project structure and essential templates."""
    from vibe_tools.setup import maybe_init_git
    from vibe_tools.templates import TEMPLATES
    import click

    maybe_init_git()

    # First, migrate any existing files from root to implementation/
    migrate_to_project_dir()

    # Ensure structure exists
    ensure_project_structure()
    ensure_dir(VIBE_PROJECT_DIR)

    # Create config.json if it doesn't exist
    if not CONFIG_FILE.exists():
        default_config = {
            "ralph": {"review": True, "tests": True, "auto_merge": False},
            "default_budget": 5.0,
            "verbose": False,
            "coverage_targets": {"backend": 85, "frontend": 85, "infra": 85},
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
    ensure_dir(PRD_DIR)
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
    """Get services from dev_environment.yaml, dev_environment.md, or Makefile."""
    services = []

    # Try dev_environment.yaml first
    build_file = DEV_ENV_CURRENT if DEV_ENV_CURRENT.exists() else DEV_ENV
    if build_file.exists():
        try:
            build_config = safe_yaml_load(build_file.read_text())
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


def test_build_services(debug=False):
    """Test that services defined in build config can actually start and respond."""
    import time

    services = get_services()
    if not services:
        logger.debug("No services found to test")
        logger.info("  ⚠️  No services configured to test")
        return False

    # Check and fix kubeconfig if skaffold is being used
    if uses_skaffold(services):
        logger.info("  🔍 Detected skaffold usage, checking kubeconfig...")
        if fix_kubeconfig_api_version():
            logger.info("  ✅ Updated kubeconfig to use v1beta1 API version")
        else:
            logger.debug("Kubeconfig API version check completed (no changes needed)")

    logger.info(f"  📋 Found {len(services)} service(s) to test")
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
                    logger.info(f"  ✓ Started {service_name} (PID: {process.pid})")
                    logger.debug(
                        f"Service {service_name} started with PID {process.pid}, command: {start_cmd}"
                    )
                    time.sleep(0.5)  # Give it a moment
                except Exception as e:
                    logger.warning(f"  ✗ Failed to start {service_name}: {e}")
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
                        logger.info(f"  ✓ Started {service_name} (PID: {process.pid})")
                        logger.debug(
                            f"Service {service_name} started with PID {process.pid}, command: {start_cmd}"
                        )
                        time.sleep(0.5)
                    except Exception as e:
                        logger.warning(f"  ✗ Failed to start {service_name}: {e}")
                        logger.debug(
                            f"Service {service_name} startup error: {e}", exc_info=True
                        )
                else:
                    logger.warning(
                        f"  ✗ Command not found for {service_name}: {cmd_parts[0]}"
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
                logger.warning(
                    f"  ✗ Service {service_name} exited immediately with code {exit_code}"
                )

        # Check if services are actually running
        logger.info("  🔍 Checking service status...")
        tracked_pids = load_pids()
        running_count = 0
        failed_services = []

        # First check the directly started processes
        for service_name, process in started_processes:
            if process.poll() is None:  # Still running
                is_running = True
                running_count += 1
                logger.info(
                    f"  ✓ {service_name} is running - started process (PID: {process.pid})"
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
                        logger.info(f"  ✓ {service_name} is running - {running_reason}")
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
                            logger.info(
                                f"  ✓ {service_name} is running - {running_reason}"
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
                            logger.info(
                                f"  ✓ {service_name} is running - {running_reason}"
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
                    logger.warning(
                        f"  ✗ {service_name} is not running - No PID information found (service may not have started)"
                    )
                elif not background_services and not main_pid and not process_name:
                    logger.warning(
                        f"  ✗ {service_name} is not running - No PID tracking data available"
                    )
                else:
                    logger.warning(
                        f"  ✗ {service_name} is not running - Process not found"
                    )

        # Check if URLs are responding
        logger.info("  🌐 Checking URL endpoints...")
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
                    logger.info(f"  ✓ {url_key} ({url}) is responding")
                    logger.debug(f"URL {url_key} ({url}) responded successfully")
                else:
                    failed_urls.append((url_key, url))
                    logger.warning(f"  ✗ {url_key} ({url}) is not responding")
                    logger.debug(
                        f"URL {url_key} ({url}) failed to respond (connection timeout or refused)"
                    )
            except Exception as e:
                failed_urls.append((url_key, url))
                logger.warning(f"  ✗ {url_key} ({url}) check failed: {e}")
                logger.debug(f"URL {url_key} ({url}) check error: {e}", exc_info=True)

        # Consider success if at least one service is running or one URL is responding
        success = running_count > 0 or responding_urls > 0

        # Summary logging - always log
        logger.info("  📊 Test Summary:")
        logger.info(f"     Services: {running_count}/{len(services)} running")
        if failed_services:
            logger.info(f"     Failed services: {', '.join(failed_services)}")
        logger.info(f"     URLs: {responding_urls}/{len(urls)} responding")
        if failed_urls:
            failed_url_list = [f"{key} ({url})" for key, url in failed_urls]
            logger.info(f"     Failed URLs: {', '.join(failed_url_list)}")

        if success:
            logger.info(
                "  ✅ Service test PASSED - At least one service or URL is responding"
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
            logger.warning(f"  ✗ Service test FAILED - {reason}")
            logger.debug(
                f"Service test failed: {running_count} service(s) running, {responding_urls} URL(s) responding"
            )

        return success

    except Exception as e:
        logger.error(f"  ❌ Error testing services: {e}")
        logger.debug(f"Service test exception: {e}", exc_info=True)
        return False


def command_exists(cmd):
    """Check if a command exists in PATH."""
    import shutil

    return shutil.which(cmd) is not None


def is_tool_available(tool: str) -> bool:
    """Checks if a tool is available in the system PATH."""
    return shutil.which(tool) is not None


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
    """Syncs project configuration to the .env file."""
    config = load_config()
    env_file = find_dotenv() or ".env"

    # This is a simplified version for now to satisfy imports
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            f.write("# Vibe-Tools Environment\n")

    # Add logic if needed, but for now just ensure it exists
    out_info("Syncing .env file...")


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


def get_latest_context_file(pattern):
    """Finds the latest file matching the pattern in PRD_DIR recursively."""
    # Handle the pattern to be more flexible (e.g. "infra_*.yaml" -> "prd_infra_*.yaml")
    search_pattern = pattern
    if not search_pattern.startswith("prd_") and not search_pattern.startswith("*"):
        search_pattern = f"prd_{search_pattern}"

    files = list(PRD_DIR.rglob(search_pattern))
    if not files:
        return "NOT FOUND"

    # Sort by name (which includes the ## prefix)
    latest = sorted(files)[-1]
    return latest.read_text()


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


def get_prd_inconsistencies():
    """Returns a list of PRDs where MD location and YAML location don't match."""
    inconsistencies = []
    
    # 1. Get all PRD info
    prd_info = collect_all_prd_info()
    
    for info in prd_info:
        if not info["has_md"] or not info["has_yaml"]:
            continue
            
        md_path = info["md_path"]
        yaml_path = info["yaml_path"]
        
        # Determine expected YAML base dir based on MD location
        if PLANNING_HISTORY_DIR in md_path.parents or md_path.parent == PLANNING_HISTORY_DIR:
            expected_base = PRD_DONE_DIR
        elif PLANNING_REJECTED_DIR in md_path.parents or md_path.parent == PLANNING_REJECTED_DIR:
            expected_base = PRD_FAILED_DIR
        else:
            expected_base = PRD_PROCESSING_DIR
            
        if expected_base not in yaml_path.parents and yaml_path.parent != expected_base:
            inconsistencies.append({
                "name": info["name"],
                "md_path": md_path,
                "yaml_path": yaml_path,
                "expected_base": expected_base,
                "current_base": yaml_path.parent
            })
            
    return inconsistencies


def fix_prd_inconsistencies(inconsistencies, prefer_yaml=True):
    """Fixes PRD location inconsistencies by moving YAML files and updating state.json."""
    if not inconsistencies:
        return
        
    state = load_project_state()
    completed_prds = set(state.get("completed_prds", []))
    
    for inc in inconsistencies:
        yaml_path = inc["yaml_path"]
        expected_base = inc["expected_base"]
        
        # 1. Move the YAML file
        ensure_dir(expected_base)
        target_path = expected_base / yaml_path.name
        
        if not target_path.exists():
            logger.info(f"Moving {yaml_path.name} from {yaml_path.parent} to {expected_base}")
            shutil.move(str(yaml_path), str(target_path))
        else:
            logger.warning(f"Target path {target_path} already exists. Deleting source {yaml_path}")
            yaml_path.unlink()
            
        # 2. Update state.json completed_prds list
        prd_id = target_path.stem
        
        if expected_base == PRD_DONE_DIR:
            completed_prds.add(prd_id)
            # Also update plan status if it exists
            if prd_id in state.get("plans", {}):
                state["plans"][prd_id]["status"] = "completed"
        else:
            if prd_id in completed_prds:
                completed_prds.remove(prd_id)
            # Reset plan status if it exists and was completed
            if prd_id in state.get("plans", {}) and state["plans"][prd_id].get("status") == "completed":
                state["plans"][prd_id]["status"] = "pending"

    state["completed_prds"] = sorted(list(completed_prds))
    save_project_state(state)


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
    logger.error(f"ISSUE: [{tag}] {message}")


def log_start(tag, *args):
    """Placeholder for logging the start of an action."""
    message = " ".join(str(a) for a in args)
    if message:
        logger.info(f"START: [{tag}] {message}")
    else:
        logger.info(f"START: {tag}")


def log_success(tag, *args):
    """Placeholder for logging the success of an action."""
    message = " ".join(str(a) for a in args)
    if message:
        logger.info(f"SUCCESS: [{tag}] {message}")
    else:
        logger.info(f"SUCCESS: {tag}")


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
            out_debug(f"\n--- DEBUG: LLM PROMPT ({model}) ---")
            out_debug(prompt)
            out_debug("--- END DEBUG ---\n")

        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )

        log_large_output(f"llm_prompt_{model}", prompt)
        log_large_output(f"llm_response_{model}", response.text)

        if debug:
            out_debug("\n--- DEBUG: LLM RESPONSE ---")
            out_debug(response.text)
            out_debug("--- END DEBUG ---\n")

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


def update_md_implementation_status(md_path, version, sequence, yaml_path):
    """Updates the MD file with its normalized implementation status."""
    if not md_path or not md_path.exists():
        return

    try:
        content = md_path.read_text()

        # Determine implementation ID and YAML name
        implementation_id = f"v{version}-{sequence:03d}"
        yaml_name = yaml_path.name if hasattr(yaml_path, "name") else str(yaml_path)

        parts = content.split("---", 2)
        if len(parts) >= 3:
            # Has existing frontmatter
            frontmatter_str = parts[1]
            body = parts[2]

            frontmatter = safe_yaml_load(frontmatter_str) or {}
            frontmatter["implementation_id"] = implementation_id
            frontmatter["implementation_yaml"] = yaml_name
            frontmatter["status"] = "normalized"

            new_frontmatter = safe_yaml_dump(frontmatter)
            # Ensure new_frontmatter ends with a newline and starts cleanly
            new_frontmatter = new_frontmatter.strip() + "\n"
            new_content = f"---\n{new_frontmatter}---{body}"
            md_path.write_text(new_content)
        else:
            # No frontmatter
            frontmatter = {
                "implementation_id": implementation_id,
                "implementation_yaml": yaml_name,
                "status": "normalized",
            }
            new_frontmatter = safe_yaml_dump(frontmatter)
            new_frontmatter = new_frontmatter.strip() + "\n"
            new_content = f"---\n{new_frontmatter}---\n\n{content.strip()}\n"
            md_path.write_text(new_content)

    except Exception as e:
        logger.warning(f"Could not update MD status for {md_path}: {e}")


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
    import re

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
    import re

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
    import re

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
    """Extract URLs from dev_environment.yaml, dev_environment.md, or Makefile."""
    urls = {}

    # Try dev_environment.yaml first
    build_file = DEV_ENV_CURRENT if DEV_ENV_CURRENT.exists() else DEV_ENV
    if build_file.exists():
        try:
            build_config = safe_yaml_load(build_file.read_text())
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
    import re

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
    import click

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
