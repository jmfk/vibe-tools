import subprocess
import time
import sys
import pathlib


def run_command(cmd, check=True, caffeinate=False):
    """Utility to run a command and return its output."""
    if caffeinate:
        cmd = ["caffeinate", "-dimsu"] + cmd
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error running command: {' '.join(cmd)}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        return result.stdout.strip(), result.returncode
    return result.stdout.strip(), result.returncode


def run_agent(cmd, caffeinate=False):
    """Runs an agent with a live progress indicator."""
    if caffeinate:
        cmd = ["caffeinate", "-dimsu"] + cmd
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    full_output, start_time = [], time.time()
    print("\n\n", end="")
    try:
        for line in iter(process.stdout.readline, ""):
            full_output.append(line)
            elapsed = int(time.time() - start_time)
            preview = line.strip()[:80]
            sys.stdout.write(
                f"\033[2A\r\033[K⏳ Agent working ({elapsed}s)...\n\033[K{preview}"
            )
            sys.stdout.flush()
    finally:
        process.stdout.close()
        process.wait()
    sys.stdout.write("\033[2A\r\033[K\n\033[K\r\033[A")
    sys.stdout.flush()
    return "".join(full_output), process.returncode


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
        print(f"Creating directory: {path}")
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
