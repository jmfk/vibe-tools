import atexit
import datetime
import hashlib
import importlib.util
import json
import logging
import os
import pathlib
import signal
import subprocess
import sys
import shutil
import time
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional

import yaml
from dotenv import find_dotenv, load_dotenv, set_key

VIBE_PROJECT_DIR = pathlib.Path("project")

PRD_DIR = VIBE_PROJECT_DIR / "prds"
PROJECT_STATE_FILE = VIBE_PROJECT_DIR / "state.json"
STATE_FILE = VIBE_PROJECT_DIR / "legacy-state.json"
LOGS_DIR = VIBE_PROJECT_DIR / "logs"
COSTS_DIR = VIBE_PROJECT_DIR / "costs"
INSTRUCTIONS_DIR = VIBE_PROJECT_DIR / "instructions"
VIBE_DATA_DIR = VIBE_PROJECT_DIR / "data"
CONFIG_FILE = VIBE_PROJECT_DIR / "config.json"
GLOBAL_VIBE_DIR = pathlib.Path.home() / ".vibe"

# Core lifecycle files
ARCHITECTURE = PRD_DIR / "architecture.yaml"
ARCHITECTURE_CURRENT = VIBE_PROJECT_DIR / "architecture-current.yaml"
ARCHITECTURE_SPEC = pathlib.Path("specs/architecture.md")
OVERVIEW = PRD_DIR / "project_overview.yaml"
INFRA = PRD_DIR / "infrastructure.yaml"
INFRA_CURRENT = VIBE_PROJECT_DIR / "infrastructure-current.yaml"
INFRA_SPEC = pathlib.Path("specs/infrastructure.md")
CICD = PRD_DIR / "cicd.yaml"
CICD_CURRENT = VIBE_PROJECT_DIR / "cicd-current.yaml"
CICD_SPEC = pathlib.Path("specs/cicd.md")
TESTING_CONFIG = PRD_DIR / "testing.yaml"
TESTING_CURRENT = VIBE_PROJECT_DIR / "testing-current.yaml"
TESTING_SPEC = pathlib.Path("specs/testing.md")
GLOBAL_CONFIG_FILE = GLOBAL_VIBE_DIR / "config.json"
ARCH_CONFIG_FILE = VIBE_PROJECT_DIR / "architect-config.json"
ARCH_SESSION_FILE = VIBE_PROJECT_DIR / "architect-session.json"
PM_CONFIG_FILE = VIBE_PROJECT_DIR / "pm-config.json"
PM_SESSION_FILE = VIBE_PROJECT_DIR / "pm-session.json"
SPECS_DIR = pathlib.Path("specs")
GLOBAL_SERVERS_FILE = GLOBAL_VIBE_DIR / "servers.json"


def log_issue(loop_name: str, iteration: int, max_iterations: int, description: str):
    """Logs a concise one-line issue to the terminal and a detailed marker to the log file."""
    from vibe_tools.cost import get_total_cost

    total_cost = get_total_cost()
    marker = f"==== ISSUE: [{loop_name.upper()}] ITERATION [{iteration}/{max_iterations}] ===="
    logger.debug(f"\n{marker}\nReason: {description}\n{'=' * len(marker)}")
    logger.info(
        f"⚠️  [{loop_name.upper()}] Iteration {iteration}/{max_iterations}: {description} (Total Cost: ${total_cost:.2f})"
    )


def log_start(loop_name: str, description: str):
    """Logs a concise one-line start message to the terminal and a marker to the log file."""
    from vibe_tools.cost import get_total_cost

    total_cost = get_total_cost()
    marker = f"==== START: [{loop_name.upper()}] ===="
    logger.debug(f"\n{marker}\nContext: {description}\n{'=' * len(marker)}")
    logger.info(
        f"🚀 [{loop_name.upper()}] Starting: {description} (Total Cost: ${total_cost:.2f})"
    )


def log_success(loop_name: str, description: str):
    """Logs a concise one-line success message to the terminal and a marker to the log file."""
    from vibe_tools.cost import get_total_cost

    total_cost = get_total_cost()
    marker = f"==== SUCCESS: [{loop_name.upper()}] ===="
    logger.debug(f"\n{marker}\nResult: {description}\n{'=' * len(marker)}")
    logger.info(
        f"✅ [{loop_name.upper()}] Completed: {description} (Total Cost: ${total_cost:.2f})"
    )


# Ensure directories exist
def ensure_project_structure():
    """Ensures that the core project directories exist."""
    VIBE_PROJECT_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)
    COSTS_DIR.mkdir(exist_ok=True)
    PRD_DIR.mkdir(exist_ok=True)
    INSTRUCTIONS_DIR.mkdir(exist_ok=True)
    GLOBAL_VIBE_DIR.mkdir(exist_ok=True)


def migrate_to_project_dir():
    """Migrates files and directories from the project root to the 'project/' directory."""
    migration_map = {
        pathlib.Path("prds"): PRD_DIR,
        pathlib.Path("project-state.json"): PROJECT_STATE_FILE,
        pathlib.Path(".ralph_state.json"): STATE_FILE,
        pathlib.Path("logs"): LOGS_DIR,
        pathlib.Path("costs"): COSTS_DIR,
        pathlib.Path("instructions"): INSTRUCTIONS_DIR,
        pathlib.Path("vibe_data"): VIBE_DATA_DIR,
        pathlib.Path(".vibe_config.json"): CONFIG_FILE,
        pathlib.Path("architecture.yaml"): ARCHITECTURE,
        pathlib.Path("architecture-current.yaml"): ARCHITECTURE_CURRENT,
        pathlib.Path("project_overview.yaml"): OVERVIEW,
        pathlib.Path("infrastructure.yaml"): INFRA,
        pathlib.Path("infrastructure-current.yaml"): INFRA_CURRENT,
        pathlib.Path("cicd.yaml"): CICD,
        pathlib.Path("cicd-current.yaml"): CICD_CURRENT,
        pathlib.Path("testing.yaml"): TESTING_CONFIG,
        pathlib.Path("testing-current.yaml"): TESTING_CURRENT,
    }

    import shutil

    for old_path, new_path in migration_map.items():
        if old_path.exists():
            # Special case: don't migrate if it's already in the project dir (shouldn't happen with these paths)
            if old_path == new_path:
                continue

            try:
                # Ensure parent directory of new_path exists
                new_path.parent.mkdir(parents=True, exist_ok=True)

                if old_path.is_dir():
                    # For directories, if the new directory already exists, move contents
                    if new_path.exists():
                        for item in old_path.iterdir():
                            target = new_path / item.name
                            if not target.exists():
                                shutil.move(str(item), str(target))
                        # Remove old empty directory if possible
                        try:
                            old_path.rmdir()
                        except OSError:
                            pass
                    else:
                        shutil.move(str(old_path), str(new_path))
                else:
                    # For files, if new_path exists, maybe don't overwrite?
                    # Usually migration means we want the old one to win if it's the one being moved.
                    if not new_path.exists():
                        shutil.move(str(old_path), str(new_path))
                    else:
                        # If both exist, we could backup the old one or just delete it if they are same
                        # For now, let's just move it and overwrite if it's a migration
                        old_path.unlink()  # Simple cleanup if new already exists
            except Exception as e:
                logger.error(f"Failed to migrate {old_path} to {new_path}: {e}")


def get_project_name():
    """Returns the project name in snake_case based on git remote or directory name."""
    if is_git_repo():
        stdout, code = run_command(["git", "remote", "get-url", "origin"], check=False)
        if code == 0 and stdout.strip():
            # Handle both https and ssh formats
            url = stdout.strip()
            if url.endswith(".git"):
                url = url[:-4]
            project_name = url.split("/")[-1].split(":")[-1]
            return project_name.lower().replace("-", "_").replace(" ", "_")

    # Fallback to directory name
    return pathlib.Path.cwd().name.lower().replace("-", "_").replace(" ", "_")


def load_config():
    """Loads and merges global and project-local configuration."""
    config = {}

    # Load global config first
    if GLOBAL_CONFIG_FILE.exists():
        try:
            config.update(json.loads(GLOBAL_CONFIG_FILE.read_text()))
        except Exception as e:
            logger.debug(f"Error loading global config: {e}")

    # Merge with local config
    if CONFIG_FILE.exists():
        try:
            local_config = json.loads(CONFIG_FILE.read_text())
            # Deep merge services if they exist in both
            if "services" in local_config and "services" in config:
                config["services"].update(local_config["services"])
                del local_config["services"]
            config.update(local_config)
        except Exception as e:
            logger.debug(f"Error loading local config: {e}")

    return config


def save_config(config, global_scope=False):
    """Saves configuration to either local or global file."""
    if global_scope:
        GLOBAL_CONFIG_FILE.write_text(json.dumps(config, indent=2))
    else:
        CONFIG_FILE.write_text(json.dumps(config, indent=2))
        ensure_gitignore(str(VIBE_PROJECT_DIR) + "/")
        ensure_gitignore(".env")


def load_project_state() -> Dict[str, Any]:
    """Loads the project state, migrating from legacy if necessary."""
    if not PROJECT_STATE_FILE.exists() and STATE_FILE.exists():
        migrate_legacy_state()

    state = {
        "project_name": get_project_name(),
        "phases": {
            "normalize": {"status": "pending", "hash": None, "depends_on": []},
            "setup": {"status": "pending", "hash": None, "depends_on": ["normalize"]},
            "deps": {"status": "pending", "hash": None, "depends_on": ["setup"]},
            "implement": {"status": "pending", "hash": None, "depends_on": ["deps"]},
            "testing": {"status": "pending", "hash": None, "depends_on": ["implement"]},
            "infra": {"status": "pending", "hash": None, "depends_on": ["testing"]},
            "cicd": {"status": "pending", "hash": None, "depends_on": ["infra"]},
            "deploy": {
                "status": "pending",
                "hash": None,
                "depends_on": ["cicd"],
            },
        },
        "plans": {},
        "branch_lineage": {},  # Maps branch -> parent_branch
        "completed_prds": [],
        "started_prds": [],
        "active_task": None,
        "version": "1.1",
    }

    if PROJECT_STATE_FILE.exists():
        try:
            stored_state = json.loads(PROJECT_STATE_FILE.read_text())
            # Basic migration/merging
            if "project_name" in stored_state:
                state["project_name"] = stored_state["project_name"]
            if "phases" in stored_state:
                for phase_id, phase_data in stored_state["phases"].items():
                    if phase_id in state["phases"]:
                        state["phases"][phase_id].update(phase_data)
            if "plans" in stored_state:
                state["plans"] = stored_state["plans"]
            if "branch_lineage" in stored_state:
                state["branch_lineage"] = stored_state["branch_lineage"]
            if "completed_prds" in stored_state:
                state["completed_prds"] = stored_state["completed_prds"]
            if "started_prds" in stored_state:
                state["started_prds"] = stored_state["started_prds"]
            if "active_task" in stored_state:
                state["active_task"] = stored_state["active_task"]
            if "version" in stored_state:
                # If we're loading an older version, we might want to trigger specific logic here
                pass
            return state
        except Exception as e:
            logger.error(f"Error loading project state: {e}")

    return state


def check_dependencies(phase_id: str, state: Dict[str, Any]) -> List[str]:
    """Returns a list of missing dependencies for a phase."""
    phases = state.get("phases", {})
    if phase_id not in phases:
        return []

    missing = []
    for dep_id in phases[phase_id].get("depends_on", []):
        dep_phase = phases.get(dep_id, {})
        if dep_phase.get("status") != "completed":
            missing.append(dep_id)

    return missing


def check_plan_dependencies(plan_id: str, state: Dict[str, Any]) -> List[str]:
    """Returns a list of missing dependencies for a plan."""
    plans = state.get("plans", {})
    if plan_id not in plans:
        return []

    missing = []
    for dep_id in plans[plan_id].get("depends_on", []):
        dep_plan = plans.get(dep_id, {})
        if dep_plan.get("status") != "completed":
            missing.append(dep_id)

    return missing


def save_project_state(state: Dict[str, Any]):
    """Saves the project state to project-state.json."""
    PROJECT_STATE_FILE.write_text(json.dumps(state, indent=2))


def migrate_legacy_state():
    """Migrates data from .ralph_state.json to project-state.json."""
    if not STATE_FILE.exists():
        return

    try:
        legacy_data = json.loads(STATE_FILE.read_text())
        new_state = load_project_state()

        # Migrate completed and started PRDs
        new_state["completed_prds"] = legacy_data.get("completed_prds", [])
        new_state["started_prds"] = legacy_data.get("started_prds", [])
        new_state["active_task"] = legacy_data.get("active_task")

        # Basic heuristic: if there are completed PRDs, maybe setup was done?
        # But we'll stay conservative and let the user run setup.

        save_project_state(new_state)
        logger.info(f"✅ Migrated legacy state to {PROJECT_STATE_FILE}")
        # We keep the old file for safety for now, or we could delete it.
        # STATE_FILE.unlink()
    except Exception as e:
        logger.error(f"Failed to migrate legacy state: {e}")


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
    GLOBAL_SERVERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    GLOBAL_SERVERS_FILE.write_text(json.dumps(servers, indent=2))


def get_google_api_key():
    """Retrieves the Google API Key from .env or environment variables."""
    load_dotenv(find_dotenv() or ".env")
    return os.environ.get("GOOGLE_API_KEY")


def save_google_api_key(key):
    """Saves the Google API Key to the .env file."""
    env_file = find_dotenv() or ".env"
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            f.write("")
    set_key(env_file, "GOOGLE_API_KEY", key)
    ensure_gitignore(".env")


def get_cursor_api_key():
    """Retrieves the Cursor API Key from .env or environment variables."""
    load_dotenv(find_dotenv() or ".env")
    return os.environ.get("CURSOR_API_KEY")


def save_cursor_api_key(key):
    """Saves the Cursor API Key to the .env file."""
    env_file = find_dotenv() or ".env"
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            f.write("")
    set_key(env_file, "CURSOR_API_KEY", key)
    ensure_gitignore(".env")


# Setup logger
logger = logging.getLogger("vibe")
logger.setLevel(logging.DEBUG)

# Globals to be initialized by setup_logging
LOG_FILE = None
file_handler = None
stream_handler = None


def setup_logging(command_name):
    """Initializes logging for a specific command run."""
    global LOG_FILE, file_handler, stream_handler

    # Ensure LOGS_DIR exists before creating the log file
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Generate timestamped log filename with command name
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    LOG_FILE = LOGS_DIR / f"{timestamp}_vibe_{command_name}.log"

    # File handler
    file_handler = RotatingFileHandler(LOG_FILE, backupCount=5)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(file_handler)

    # Stream handler (console)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(stream_handler)

    return LOG_FILE


def set_console_level(level):
    """Sets the console output level."""
    if stream_handler:
        stream_handler.setLevel(level)


# Flag to track if an agent was called
_agent_called = False


def _cleanup_log():
    """Deletes the log file if it's empty."""
    global LOG_FILE, file_handler
    if not LOG_FILE:
        return

    try:
        # Delete only if the file is empty
        if LOG_FILE.exists() and LOG_FILE.stat().st_size == 0:
            # Close handler to release file lock
            if file_handler:
                file_handler.close()
                logger.removeHandler(file_handler)
            if LOG_FILE.exists():
                LOG_FILE.unlink()
    except Exception:
        pass


atexit.register(_cleanup_log)


def enable_console_debug():
    """Sets the console output level to DEBUG."""
    if stream_handler:
        stream_handler.setLevel(logging.DEBUG)
        logger.debug("Console debug logging enabled.")


def rotate_log():
    """Rotates the log file if it exists and is not empty."""
    if LOG_FILE and LOG_FILE.exists() and LOG_FILE.stat().st_size > 0:
        if file_handler:
            file_handler.doRollover()


def is_merged(branch_name):
    """Checks if a branch is merged into main."""
    main_branch = get_main_branch()
    _, code = run_command(
        ["git", "merge-base", "--is-ancestor", branch_name, main_branch], check=False
    )
    return code == 0


def run_llm(prompt: str, model: str = "gemini-3-flash", json_mode: bool = False) -> str:
    """Runs a direct LLM call using dspy CLI."""
    if shutil.which("dspy") is None:
        # Fallback to python module if CLI not in path
        cmd = [sys.executable, "-m", "dspy.cli"]
    else:
        cmd = ["dspy"]

    cmd.extend(["--model", model])
    if json_mode:
        cmd.append("--json")

    api_key = get_google_api_key()
    env = os.environ.copy()
    if api_key:
        env["GOOGLE_API_KEY"] = api_key

    payload = {"prompt": prompt}

    # Use subprocess.run directly for simple synchronous call
    result = subprocess.run(
        cmd, input=json.dumps(payload), capture_output=True, text=True, env=env
    )

    if result.returncode != 0:
        logger.error(f"LLM call failed: {result.stderr}")
        raise RuntimeError(f"LLM call failed: {result.stderr}")

    output = result.stdout.strip()
    if json_mode:
        try:
            # Extract JSON from output
            import re

            match = re.search(r"(\{.*\})", output, re.DOTALL)
            if match:
                return match.group(1)
        except Exception:
            pass

    return output


def run_command(cmd, check=True, caffeinate=False):
    """Utility to run a command and return its output."""
    if caffeinate:
        cmd = ["caffeinate", "-dimsu"] + cmd

    # Use logger.debug for the "Running command" message so it's hidden by default
    logger.debug(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Debug level logging for full command output
    logger.debug(f"Command finished with return code: {result.returncode}")
    if result.stdout:
        logger.debug(f"STDOUT:\n{result.stdout.strip()}")
    if result.stderr:
        logger.debug(f"STDERR:\n{result.stderr.strip()}")

    if check and result.returncode != 0:
        logger.error(f"Error running command: {' '.join(cmd)}")
        if not logger.isEnabledFor(logging.DEBUG):
            # If not in debug mode, at least log the error output to info/error
            logger.error(f"STDOUT: {result.stdout.strip()}")
            logger.error(f"STDERR: {result.stderr.strip()}")
        return result.stdout.strip(), result.returncode
    return result.stdout.strip(), result.returncode


def run_agent(cmd, caffeinate=False, stream=False):
    """Runs an agent with a live progress indicator or streaming output."""
    global _agent_called
    _agent_called = True
    if caffeinate:
        cmd = ["caffeinate", "-dimsu"] + cmd

    # Use logger.debug for the "Running agent" message
    logger.debug(f"Running agent: {' '.join(cmd)}")

    # Use process groups to ensure children are killed on interrupt (Unix only)
    popen_kwargs: Dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "bufsize": 1,
    }
    if os.name != "nt":
        popen_kwargs["preexec_fn"] = os.setsid

    process = subprocess.Popen(cmd, **popen_kwargs)
    full_output, start_time = [], time.time()

    assert process.stdout is not None
    try:
        for line in iter(process.stdout.readline, ""):
            full_output.append(line)
            elapsed = int(time.time() - start_time)
            preview = line.strip()[:80]

            if stream:
                # Direct streaming to stdout
                sys.stdout.write(line)
                sys.stdout.flush()
            else:
                # Live progress to stdout (bypassing file log for spammy progress)
                from vibe_tools.cost import get_total_cost

                total_cost = get_total_cost()
                sys.stdout.write(
                    f"\r\033[K⏳ Agent working ({elapsed}s) | Cost: ${total_cost:.2f} | [CTRL-C] to stop | {preview}"
                )
                sys.stdout.flush()

            # Also log to debug file immediately
            logger.debug(f"AGENT_LIVE: {line.strip()}")
    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user. Cleaning up agent process...")
        if os.name != "nt":
            try:
                pgid = os.getpgid(process.pid)
                os.killpg(pgid, signal.SIGTERM)
                # Wait a bit for graceful exit then force kill if needed
                time.sleep(0.5)
                if process.poll() is None:
                    os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.terminate()
        process.wait()
        sys.stdout.write("\n")
        raise
    finally:
        if process.stdout:
            process.stdout.close()
        process.wait()

    sys.stdout.write("\r\033[K")
    sys.stdout.flush()

    output = "".join(full_output)
    logger.info(f"Agent finished with exit code: {process.returncode}")

    # Log full agent output to debug level (which goes to file)
    logger.debug(f"\n--- AGENT OUTPUT START ---\n{output}\n--- AGENT OUTPUT END ---\n")

    return output, process.returncode


def get_agent_processes() -> List[Dict[str, Any]]:
    """Returns a list of active agent processes."""
    targets = ["cursor-agent", "claude", "antigravity", "caffeinate -dimsu"]
    processes = []

    try:
        # ps -eo pid,ppid,start,command
        # We'll use pgrep -fl to find matching processes
        for target in targets:
            stdout, code = run_command(["pgrep", "-fl", target], check=False)
            if code == 0 and stdout.strip():
                for line in stdout.strip().splitlines():
                    parts = line.split(maxsplit=1)
                    if len(parts) == 2:
                        pid, cmd = parts
                        processes.append({"pid": pid, "command": cmd, "target": target})
    except Exception as e:
        logger.error(f"Error getting agent processes: {e}")

    return processes


def cleanup_stale_processes():
    """Kills stale pytest, cursor-agent, and caffeinate processes."""
    logger.info("Cleaning up stale processes associated with vibe-tools...")

    targets = ["pytest", "cursor-agent", "claude", "antigravity", "caffeinate -dimsu"]
    killed = []

    for target in targets:
        # Check if any processes exist before killing
        stdout, code = run_command(["pgrep", "-f", target], check=False)
        if code == 0 and stdout.strip():
            logger.info(f"Killing '{target}' processes...")
            subprocess.run(["pkill", "-f", target], check=False)
            killed.append(target)

    logger.info("Cleanup complete.")
    return killed


def get_agent_command(agent_type, prompt):
    """Returns the command list for the specified agent and prompt."""
    if agent_type == "cursor-agent":
        return [
            "cursor-agent",
            "--model",
            "gemini-3-flash",
            "--print",
            "--force",
            "--approve-mcps",
            prompt,
        ]
    elif agent_type == "claude":
        # Assuming 'claude' command for Claude Code
        return ["claude", "-p", prompt]
    elif agent_type == "antigravity":
        # Assuming 'antigravity' command
        return ["antigravity", prompt]
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")


def ensure_dir(path: pathlib.Path):
    if not path.exists():
        logger.info(f"Creating directory: {path}")
        path.mkdir(parents=True, exist_ok=True)


def check_env_health() -> bool:
    """Checks if the current environment is healthy and correctly configured."""
    config = load_config()
    env_config = config.get("env")

    # 1. Check if backend or project package is importable
    project_name = get_project_name()
    package_found = False

    for pkg in ["backend", project_name]:
        if importlib.util.find_spec(pkg):
            logger.debug(f"✅ '{pkg}' package is importable.")
            package_found = True
            break

    if not package_found:
        logger.warning(
            f"❌ Neither 'backend' nor '{project_name}' package is importable. Project structure may be broken."
        )
        return False

    # 2. Check for essential tools
    missing_tools = []

    # Backend tools
    for tool in ["python3", "pip", "ruff", "pytest"]:
        _, code = run_command([tool, "--version"], check=False)
        if code != 0:
            missing_tools.append(tool)

    # Frontend tools (if frontend directory exists)
    if pathlib.Path("frontend").exists():
        for tool in ["node", "npm", "npx"]:
            _, code = run_command([tool, "--version"], check=False)
            if code != 0:
                missing_tools.append(tool)

    if missing_tools:
        logger.warning(f"❌ Missing essential tools: {', '.join(missing_tools)}")
        return False

    # 3. Check for package structure
    for pkg_dir in ["backend", project_name]:
        path = pathlib.Path(pkg_dir)
        if path.exists() and not (path / "__init__.py").exists():
            logger.warning(f"❌ Missing '{pkg_dir}/__init__.py'.")
            return False

    if not VIBE_DATA_DIR.exists():
        logger.warning(f"❌ Missing local data directory '{VIBE_DATA_DIR}/'.")
        return False

    # 4. If managed env is configured, check if we're in it
    if env_config:
        venv_name = env_config.get("venv_name")
        if venv_name:
            current_prefix = sys.prefix
            # If we are running via pipx, the sys.prefix will be the pipx venv
            # but we want to know if the *active* pyenv environment is correct
            # or if we are at least in a context where the project venv is intended
            if "pipx" in current_prefix:
                # We are running globally via pipx. We should check if the
                # user has activated their project venv or if we are in the project dir
                # For now, let's look at the PYENV_VERSION or similar env vars
                import os

                pyenv_version = os.environ.get("PYENV_VERSION") or os.environ.get(
                    "VIRTUAL_ENV"
                )
                if (
                    venv_name not in str(pyenv_version)
                    and venv_name not in current_prefix
                ):
                    logger.warning(
                        f"⚠️  Managed environment '{venv_name}' is configured but not active."
                    )
                    logger.warning(
                        "   Note: You are running 'vibe' via pipx global install."
                    )
                    logger.warning(
                        f"   Please run 'pyenv activate {venv_name}' or ensure it's set in .python-version"
                    )
                    return False
            elif venv_name not in current_prefix:
                logger.warning(
                    f"⚠️  Managed environment '{venv_name}' is configured but not active."
                )
                logger.warning(f"   Current environment: {current_prefix}")
                return False

            logger.debug("✅ Environment check passed.")

    return True


def get_file_hash(filepath: pathlib.Path) -> Optional[str]:
    """Returns the SHA256 hash of a file."""
    if not filepath.exists():
        return None
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_prompt(prompt_filename: str) -> str:
    """Retrieves a prompt template from prompts/ directory (override) or from templates.py (fallback)."""
    from vibe_tools.templates import TEMPLATES

    override_path = pathlib.Path("prompts") / prompt_filename
    if override_path.exists():
        return override_path.read_text()

    if prompt_filename in TEMPLATES:
        return TEMPLATES[prompt_filename]

    raise FileNotFoundError(
        f"Prompt template '{prompt_filename}' not found in 'prompts/' or 'TEMPLATES'."
    )


def is_git_repo():
    try:
        # Check if we are inside a git repository
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        # git command not found
        return False


def get_main_branch():
    """Returns 'main' or 'master' depending on which one exists."""
    _, code = run_command(["git", "rev-parse", "--verify", "main"], check=False)
    if code == 0:
        return "main"
    _, code = run_command(["git", "rev-parse", "--verify", "master"], check=False)
    if code == 0:
        return "master"
    return "main"  # Default fallback


def get_automerge_branch(config=None):
    """Returns the configured automerge branch or defaults to 'automerge'."""
    if config is None:
        config = load_config()

    ralph_config = config.get("ralph", {})
    return ralph_config.get("automerge_branch", "automerge")


def get_changed_files(base_branch=None):
    """Returns files changed relative to the base branch."""
    if not is_git_repo():
        return []

    if base_branch is None:
        base_branch = get_main_branch()
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


def switch_to_main():
    """Helper to commit dirty changes on feature branches before switching to main."""
    main_branch = get_main_branch()
    if is_dirty():
        current_branch, _ = run_command(
            ["git", "branch", "--show-current"], check=False
        )
        current_branch = current_branch.strip()
        if current_branch and current_branch != main_branch:
            logger.info(
                f"Uncommitted changes detected on '{current_branch}'. Committing before switching to '{main_branch}'..."
            )
            run_command(["git", "add", "."], check=False)
            run_command(
                [
                    "git",
                    "commit",
                    "-m",
                    f"vibe: automatic commit of partial work on {current_branch}",
                ],
                check=False,
            )
        else:
            logger.error(
                f"Uncommitted changes detected on '{main_branch}'. Refusing to auto-commit to main branch to keep it clean."
            )
            return

    logger.debug(f"Switching to {main_branch}...")
    stdout, code = run_command(["git", "checkout", main_branch], check=False)
    if code != 0:
        logger.error(f"Failed to switch to {main_branch}: {stdout}")


def ensure_gitignore(entry: str):
    """Ensures that a specific entry exists in .gitignore."""
    gitignore = pathlib.Path(".gitignore")
    if not gitignore.exists():
        gitignore.write_text(f"{entry}\n")
        logger.info(f"Added {entry} to new .gitignore")
        return

    content = gitignore.read_text()
    if entry not in content.splitlines():
        with gitignore.open("a") as f:
            f.write(f"\n{entry}\n")
        logger.info(f"Added {entry} to .gitignore")


def sync_env_file():
    """Generates or updates the .env file based on the current configuration."""
    config = load_config()
    services = config.get("services", {})
    env_lines = []

    # 1. Database (Postgres)
    pg = services.get("postgres")
    if pg:
        env_lines.append(f"DB_HOST={pg.get('host', 'localhost')}")
        env_lines.append(f"DB_PORT={pg.get('port', 5432)}")
        env_lines.append(f"DB_USER={pg.get('user', 'postgres')}")
        env_lines.append(f"DB_PASSWORD={pg.get('password', 'postgres')}")
        env_lines.append(f"DB_NAME={pg.get('database', get_project_name())}")
        # Tortoise-ORM compatible URL
        db_url = f"postgres://{pg.get('user')}:{pg.get('password')}@{pg.get('host')}:{pg.get('port')}/{pg.get('database')}"
        env_lines.append(f"DATABASE_URL={db_url}")
        env_lines.append("")

    # 2. Redis
    redis = services.get("redis")
    if redis:
        env_lines.append(f"REDIS_HOST={redis.get('host', 'localhost')}")
        env_lines.append(f"REDIS_PORT={redis.get('port', 6379)}")
        password = redis.get("password", "")
        env_lines.append(f"REDIS_PASSWORD={password}")
        env_lines.append(f"REDIS_DB={redis.get('database', 0)}")
        redis_url = f"redis://{':' + password + '@' if password else ''}{redis.get('host')}:{redis.get('port')}/{redis.get('database')}"
        env_lines.append(f"REDIS_URL={redis_url}")
        env_lines.append("")

    # 3. Google API Key
    google_key = get_google_api_key()
    if google_key:
        env_lines.append(f"GOOGLE_API_KEY={google_key}")
        env_lines.append("")

    # 4. Local Storage
    if VIBE_DATA_DIR.exists():
        env_lines.append(f"VIBE_DATA_DIR={VIBE_DATA_DIR.absolute()}")
        env_lines.append("")

    # 5. S3 / Object Store
    s3_linode = services.get("s3-linode")
    s3_aws = services.get("s3-aws")
    s3 = s3_linode or s3_aws
    if s3:
        env_lines.append(f"S3_HOST={s3.get('host')}")
        env_lines.append(f"S3_PORT={s3.get('port')}")
        env_lines.append(f"S3_ACCESS_KEY={s3.get('access_key')}")
        env_lines.append(f"S3_SECRET_KEY={s3.get('secret_key')}")
        env_lines.append(f"S3_REGION={s3.get('region')}")
        env_lines.append("")

    # 5. RabbitMQ
    rmq = services.get("rabbitmq")
    if rmq:
        env_lines.append(f"RABBITMQ_HOST={rmq.get('host')}")
        env_lines.append(f"RABBITMQ_PORT={rmq.get('port')}")
        env_lines.append(f"RABBITMQ_USER={rmq.get('user')}")
        env_lines.append(f"RABBITMQ_PASSWORD={rmq.get('password')}")
        env_lines.append("")

    # Write to .env
    env_file = pathlib.Path(".env")
    if env_lines:
        content = "# Generated by vibe-setup\n" + "\n".join(env_lines)
        env_file.write_text(content)
        ensure_gitignore(".env")
        logger.info(f"✅ Updated {env_file} with current service configuration.")


def collect_prd_files():
    """Returns all PRD files in PRD_DIR starting with prd_."""
    return sorted(list(PRD_DIR.glob("prd_*.yaml")), key=lambda path: path.name)


def collect_all_prd_info() -> List[Dict[str, Any]]:
    """
    Collects information about all PRDs from both specs/ and project/prds/.
    Returns a list of dicts with: name, has_md, has_yaml, md_path, yaml_path
    """
    import re

    prd_info = {}

    # 1. Scan specs/ for .md files
    if SPECS_DIR.exists():
        for md_file in SPECS_DIR.rglob("*.md"):
            # Exclude special global truth files if they are not meant to be listed as PRDs
            # But the requirement says "if the prd has a .yaml or a .md"
            stem = md_file.stem
            clean_name = stem.lower()
            while True:
                new_name = re.sub(r"^prd[-_ ]?", "", clean_name)
                if new_name == clean_name:
                    break
                clean_name = new_name
            clean_name = re.sub(r"[- ]", "_", clean_name)

            if clean_name not in prd_info:
                prd_info[clean_name] = {
                    "name": clean_name,
                    "has_md": True,
                    "has_yaml": False,
                    "md_path": md_file,
                    "yaml_path": None,
                }
            else:
                prd_info[clean_name]["has_md"] = True
                prd_info[clean_name]["md_path"] = md_file

    # 2. Scan project/prds/ for .yaml files
    if PRD_DIR.exists():
        for yaml_file in PRD_DIR.glob("*.yaml"):
            stem = yaml_file.stem
            clean_name = stem.lower()
            # If it's a prd_*.yaml, clean the prefix
            if clean_name.startswith("prd_"):
                while True:
                    new_name = re.sub(r"^prd[-_ ]?", "", clean_name)
                    if new_name == clean_name:
                        break
                    clean_name = new_name
            clean_name = re.sub(r"[- ]", "_", clean_name)

            if clean_name not in prd_info:
                prd_info[clean_name] = {
                    "name": clean_name,
                    "has_md": False,
                    "has_yaml": True,
                    "md_path": None,
                    "yaml_path": yaml_file,
                }
            else:
                prd_info[clean_name]["has_yaml"] = True
                prd_info[clean_name]["yaml_path"] = yaml_file

    # Sort by name
    return sorted(prd_info.values(), key=lambda x: x["name"])


def reset_prd_state(project_name: str) -> List[str]:
    """
    Resets the state of a PRD and deletes its branch.
    Returns a list of messages describing the actions taken.
    """
    messages = []
    state = load_project_state()
    state_changed = False

    # 1. Clear active task
    active_task = state.get("active_task")
    if active_task and active_task.get("prd_name") == project_name:
        state["active_task"] = None
        state_changed = True
        messages.append(f"Cleared active task for {project_name}.")

    # 2. Remove from completed_prds
    if project_name in state.get("completed_prds", []):
        state["completed_prds"].remove(project_name)
        state_changed = True
        messages.append(f"Removed {project_name} from completed PRDs.")

    # 3. Remove from started_prds
    if project_name in state.get("started_prds", []):
        state["started_prds"].remove(project_name)
        state_changed = True
        messages.append(f"Removed {project_name} from started PRDs.")

    if state_changed:
        save_project_state(state)

    # 4. Handle git branch
    config = load_config()
    auto_merge = config.get("ralph", {}).get("auto_merge", False)
    if auto_merge:
        branch_name = get_automerge_branch(config)
    else:
        branch_name = f"feature/{project_name}"

    # Do not delete the automerge branch
    automerge_branch = get_automerge_branch(config)
    if branch_name == automerge_branch:
        messages.append(f"Skipping deletion of automerge branch {branch_name}.")
        return messages

    _, check_branch = run_command(
        ["git", "rev-parse", "--verify", branch_name], check=False
    )
    if check_branch == 0:
        stdout, _ = run_command(["git", "branch", "--show-current"], check=False)
        if stdout.strip() == branch_name:
            switch_to_main()
            messages.append(f"Switched from {branch_name} to the main branch.")

        _, code = run_command(["git", "branch", "-D", branch_name], check=False)
        if code == 0:
            messages.append(f"Deleted branch {branch_name}.")
        else:
            messages.append(f"Failed to delete branch {branch_name}.")

    return messages


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


def get_vibe_status_report():
    """Generates a comprehensive status report of the system."""
    import click

    from vibe_tools.cost import get_total_cost
    from vibe_tools.servers import get_container_status, get_server_configs

    state = load_project_state()
    report = []
    report.append(click.style("\n=== VIBE PROJECT STATUS ===", fg="cyan", bold=True))

    # 1. Project Info
    project_name = state.get("project_name", get_project_name())
    version = state.get("version", "1.0")
    report.append(f"\n{click.style('PROJECT:', bold=True)} {project_name} (v{version})")
    report.append(f"{click.style('DIRECTORY:', bold=True)} {pathlib.Path.cwd()}")

    active_task = state.get("active_task")
    if active_task:
        report.append(
            f"{click.style('ACTIVE TASK:', bold=True)} {click.style(active_task, fg='yellow')}"
        )

    # 2. Lifecycle Progress
    report.append(click.style("\nLIFECYCLE PROGRESS:", fg="yellow", bold=True))
    phases = state.get("phases", {})
    # Map phase to its corresponding desired file for sync check
    phase_files = {
        "setup": (ARCHITECTURE, ARCHITECTURE_CURRENT),
        "infra": (INFRA, INFRA_CURRENT),
        "cicd": (CICD, CICD_CURRENT),
        "testing": (TESTING_CONFIG, TESTING_CURRENT),
    }

    order = [
        "normalize",
        "setup",
        "deps",
        "implement",
        "testing",
        "infra",
        "cicd",
        "deploy",
    ]

    next_action = None
    for phase_id in order:
        phase = phases.get(phase_id, {})
        status = phase.get("status", "pending")

        # Dynamic status calculation for implementation phase
        if phase_id == "implement":
            all_plans = state.get("plans", {})
            if all_plans:
                completed_count = sum(
                    1 for p in all_plans.values() if p.get("status") == "completed"
                )
                total_count = len(all_plans)
                if completed_count == total_count:
                    status = "completed"
                elif completed_count > 0:
                    status = "in_progress"
                else:
                    status = "pending"

        sync_status = ""
        if phase_id in phase_files:
            desired_file, current_file = phase_files[phase_id]
            if desired_file.exists() and current_file.exists():
                if get_file_hash(desired_file) == get_file_hash(current_file):
                    sync_status = click.style(" (In Sync)", fg="green", dim=True)
                else:
                    sync_status = click.style(" (Out of Sync)", fg="yellow", dim=True)
            elif desired_file.exists():
                sync_status = click.style(" (Needs Init)", fg="red", dim=True)
            else:
                sync_status = click.style(" (Missing YAML)", fg="red", dim=True)

        if status == "completed":
            status_display = click.style("✅ DONE", fg="green") + sync_status
        elif status == "in_progress":
            status_display = click.style("⏳ IN_PROGRESS", fg="blue") + sync_status
            if not next_action:
                next_action = f"vibe {phase_id}"
        else:
            status_display = (
                click.style("⚪ PENDING", fg="white", dim=True) + sync_status
            )
            # Special hint for normalize phase if nothing is in specs/
            if phase_id == "normalize":
                if not SPECS_DIR.exists() or not list(SPECS_DIR.rglob("*.md")):
                    status_display += (
                        f" {click.style('(Run vibe pm)', fg='white', dim=True)}"
                    )

            if not next_action:
                next_action = f"vibe {phase_id}"

        report.append(f"  - {phase_id:<15} {status_display}")

    # 3. Core Configuration
    report.append(click.style("\nCORE CONFIGURATION:", fg="yellow", bold=True))
    core_files = [
        ("Architecture", ARCHITECTURE, "vibe architect"),
        ("Project Overview", OVERVIEW, None),
        ("Infrastructure", INFRA, "vibe architect"),
        ("CI/CD", CICD, "vibe architect"),
        ("Testing", TESTING_CONFIG, "vibe architect"),
    ]
    for label, path, fix_cmd in core_files:
        if path.exists():
            status = click.style("✅ Found", fg="green")
            report.append(f"  - {label:<20} {status}")
        else:
            status = click.style("⚪ Missing", fg="white", dim=True)
            suggestion = f" (Run '{fix_cmd}' then 'vibe normalize')" if fix_cmd else ""
            report.append(f"  - {label:<20} {status}{suggestion}")

    # 4. Planning & Implementation
    report.append(click.style("\nIMPLEMENTATION PLANS:", fg="yellow", bold=True))
    # Granular plans from project-state.json (Source of Truth)
    state_plans = state.get("plans", {})
    if state_plans:
        # Sort plans by ID if possible, or just iterate
        for plan_id, plan_info in state_plans.items():
            status = plan_info.get("status", "pending")
            if status == "completed":
                status_display = click.style("✅ DONE", fg="green")
            elif status == "in_progress":
                status_display = click.style("⏳ IN_PROGRESS", fg="blue")
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
    for phase_id in order:
        if phase_id == "implement":
            all_plans = state.get("plans", {})
            if all_plans:
                # Find the first pending plan
                for pid, pinfo in all_plans.items():
                    if pinfo.get("status") == "pending":
                        next_plan_id = pid
                        break
        if next_plan_id:
            break

    if next_plan_id:
        plan_info = state["plans"][next_plan_id]
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

    report.append("")
    return "\n".join(report)
