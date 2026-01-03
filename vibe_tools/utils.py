import subprocess
import time
import sys
import pathlib

def run_command(cmd, check=True):
    """Utility to run a command and return its output."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error running command: {' '.join(cmd)}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        return result.stdout.strip(), result.returncode
    return result.stdout.strip(), result.returncode

def run_cursor_agent(cmd):
    """Runs cursor-agent with a live progress indicator."""
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

def ensure_dir(path: pathlib.Path):
    if not path.exists():
        print(f"Creating directory: {path}")
        path.mkdir(parents=True, exist_ok=True)

