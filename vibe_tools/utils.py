import atexit
import datetime
import json
import logging
import os
import pathlib
import signal
import subprocess
import sys
import time
from dotenv import load_dotenv, find_dotenv, set_key
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional

PRD_DIR = pathlib.Path("prds")
STATE_FILE = pathlib.Path(".ralph_state.json")
LOGS_DIR = pathlib.Path("logs")
COSTS_DIR = pathlib.Path("costs")
SPECIAL_PRD_SUBDIRS = ["infra", "cicd"]
INSTRUCTIONS_DIR = pathlib.Path("instructions")
CONFIG_FILE = pathlib.Path(".vibe_config.json")
GLOBAL_VIBE_DIR = pathlib.Path.home() / ".vibe"
GLOBAL_CONFIG_FILE = GLOBAL_VIBE_DIR / "config.json"
GLOBAL_SERVERS_FILE = GLOBAL_VIBE_DIR / "servers.json"

# Ensure directories exist
LOGS_DIR.mkdir(exist_ok=True)
COSTS_DIR.mkdir(exist_ok=True)
GLOBAL_VIBE_DIR.mkdir(exist_ok=True)


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
        ensure_gitignore(".vibe_config.json")
        ensure_gitignore(".env")
        ensure_gitignore("logs/")
        ensure_gitignore(".vibe_google_creds.json")
        ensure_gitignore(".vibe_client_secrets.json")
        ensure_gitignore(".vibe_authorized_user.json")


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

    # Generate timestamped log filename with command name
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    LOG_FILE = LOGS_DIR / f"vibe_{command_name}_{timestamp}.log"

    # File handler
    file_handler = RotatingFileHandler(LOG_FILE, backupCount=5)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
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
    _, code = run_command(["git", "merge-base", "--is-ancestor", branch_name, "main"], check=False)
    return code == 0


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


def run_agent(cmd, caffeinate=False):
    """Runs an agent with a live progress indicator."""
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
            # Live progress to stdout (bypassing file log for spammy progress)
            sys.stdout.write(f"\r\033[K⏳ Agent working ({elapsed}s)... {preview}")
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


def cleanup_stale_processes():
    """Kills stale pytest, cursor-agent, and caffeinate processes."""
    logger.info("Cleaning up stale processes associated with vibe-tools...")

    targets = ["pytest", "cursor-agent", "claude", "antigravity", "caffeinate -dimsu"]

    for target in targets:
        logger.info(f"Killing '{target}' processes...")
        # Use pkill with full string matching
        subprocess.run(["pkill", "-f", target], check=False)

    logger.info("Cleanup complete.")


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

    stdout, code = run_command(["git", "ls-files", "--others", "--exclude-standard"], check=False)
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
    """Checks if the repository has uncommitted changes."""
    if not is_git_repo():
        return False
    _, code = run_command(["git", "diff", "--quiet"], check=False)
    if code != 0:
        return True
    _, code = run_command(["git", "diff", "--cached", "--quiet"], check=False)
    return code != 0


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


def collect_prd_files():
    """Returns all PRD files, including special infra/CI-CD subdirectories."""
    prd_files = list(PRD_DIR.glob("prd_*.yaml"))
    for subdir in SPECIAL_PRD_SUBDIRS:
        subdir_path = PRD_DIR / subdir
        if subdir_path.exists():
            prd_files.extend(subdir_path.glob("prd_*.yaml"))
    return sorted(prd_files, key=lambda path: path.name)


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
