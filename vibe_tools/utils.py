import subprocess
import time
import sys
import pathlib
import json
import logging
from logging.handlers import RotatingFileHandler

PRD_DIR = pathlib.Path("prds")
STATE_FILE = pathlib.Path(".ralph_state.json")
LOG_FILE = pathlib.Path("vibe.log")

# Setup logger
logger = logging.getLogger("vibe")
logger.setLevel(logging.INFO)

# File handler
file_handler = RotatingFileHandler(LOG_FILE, backupCount=5)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(file_handler)

# Stream handler
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(stream_handler)


def rotate_log():
    """Rotates the log file if it exists and is not empty."""
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > 0:
        file_handler.doRollover()


def is_merged(branch_name):
    """Checks if a branch is merged into main."""
    _, code = run_command(
        ["git", "merge-base", "--is-ancestor", branch_name, "main"], check=False
    )
    return code == 0


def run_command(cmd, check=True, caffeinate=False):
    """Utility to run a command and return its output."""
    if caffeinate:
        cmd = ["caffeinate", "-dimsu"] + cmd
    
    logger.info(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        logger.error(f"Error running command: {' '.join(cmd)}")
        logger.error(f"STDOUT: {result.stdout}")
        logger.error(f"STDERR: {result.stderr}")
        return result.stdout.strip(), result.returncode
    return result.stdout.strip(), result.returncode


def run_agent(cmd, caffeinate=False):
    """Runs an agent with a live progress indicator."""
    if caffeinate:
        cmd = ["caffeinate", "-dimsu"] + cmd
    
    logger.info(f"Running agent: {' '.join(cmd)}")
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    full_output, start_time = [], time.time()
    try:
        for line in iter(process.stdout.readline, ""):
            full_output.append(line)
            elapsed = int(time.time() - start_time)
            preview = line.strip()[:80]
            # Live progress to stdout (bypassing file log for spammy progress)
            sys.stdout.write(
                f"\r\033[K⏳ Agent working ({elapsed}s)... {preview}"
            )
            sys.stdout.flush()
    finally:
        process.stdout.close()
        process.wait()
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()
    
    output = "".join(full_output)
    logger.info(f"Agent finished with exit code: {process.returncode}")
    # Log full agent output to file only to avoid cluttering terminal
    with open(LOG_FILE, "a") as f:
        f.write(f"\n--- AGENT OUTPUT START ---\n{output}\n--- AGENT OUTPUT END ---\n")
    
    return output, process.returncode


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
