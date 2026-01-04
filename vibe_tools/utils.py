import atexit
import datetime
import logging
import os
import pathlib
import signal
import subprocess
import sys
import time
from logging.handlers import RotatingFileHandler
from typing import Any, Dict

PRD_DIR = pathlib.Path("prds")
STATE_FILE = pathlib.Path(".ralph_state.json")
LOGS_DIR = pathlib.Path("logs")
COSTS_DIR = pathlib.Path("costs")

# Ensure directories exist
LOGS_DIR.mkdir(exist_ok=True)
COSTS_DIR.mkdir(exist_ok=True)

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
