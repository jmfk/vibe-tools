import subprocess
import time
import argparse
import sys
import datetime

def run_command(cmd, check=True):
    """Utility to run a command and return its output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if check and result.returncode != 0:
            return f"Error: {result.stderr.strip()}"
        return result.stdout.strip()
    except Exception as e:
        return f"Exception: {str(e)}"


def run_cursor_agent(cmd):
    """Runs cursor-agent with a live progress indicator."""
    import sys
    import time

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


def get_status_report(interval):
    """Gathers context and calls cursor-agent to inspect progress."""
    current_branch = run_command(["git", "branch", "--show-current"])
    git_status = run_command(["git", "status", "--short"])
    last_diff = run_command(["git", "diff", "HEAD", "src/"])
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    inspection_prompt = f"""
You are a PROGRESS INSPECTOR for an automated code generation loop.
Current Time: {timestamp}
Current Branch: {current_branch}

GIT STATUS (short):
{git_status}

RECENT DIFFS (src/):
{last_diff[:2000]}  # Truncated for prompt length

TASK:
1. Identify which PRD is likely being processed (look at branch name).
2. Summarize the progress in 'src/'.
3. Detect any "BLOCKER" messages in files or signs of failure/stalling.
4. Provide a HEALTH STATUS: [HEALTHY], [STALLED], or [FAILED].
5. Keep it very concise (max 10 lines).
"""

    cmd = [
        "cursor-agent",
        "--model",
        "gemini-3-flash",
        "--print",
        "--force",
        "--approve-mcps",
        inspection_prompt
    ]
    
    print(f"\n--- Monitoring Report [{timestamp}] ---")
    output, returncode = run_cursor_agent(cmd)
    if returncode == 0:
        print(output)
    else:
        print(f"Error calling cursor-agent (Exit Code {returncode}): {output}")

def main():
    parser = argparse.ArgumentParser(description="Monitor the progress of automated generation.")
    parser.add_argument("--interval", type=int, default=60, help="Monitoring interval in seconds (default: 60)")
    args = parser.parse_args()

    print(f"Starting monitor with {args.interval}s interval. Press Ctrl+C to stop.")
    
    try:
        while True:
            get_status_report(args.interval)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main()

