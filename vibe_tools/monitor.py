import time
import datetime
import sys
import pathlib
import click
from vibe_tools.utils import run_command, run_cursor_agent

PROMPTS_DIR = pathlib.Path("prompts")
MONITOR_PROMPT_TEMPLATE = PROMPTS_DIR / "monitor_prompt.txt"

def get_status_report(interval):
    """Gathers context and calls cursor-agent to inspect progress."""
    current_branch = run_command(["git", "branch", "--show-current"])[0]
    git_status = run_command(["git", "status", "--short"])[0]
    last_diff = run_command(["git", "diff", "HEAD", "src/"])[0]
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not MONITOR_PROMPT_TEMPLATE.exists():
        print(f"Error: Monitor prompt template not found at {MONITOR_PROMPT_TEMPLATE}. Please run 'vibe init'.")
        sys.exit(1)

    prompt_base = MONITOR_PROMPT_TEMPLATE.read_text()
    inspection_prompt = prompt_base.format(
        timestamp=timestamp,
        current_branch=current_branch,
        git_status=git_status,
        last_diff=last_diff[:2000]
    )

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

def run_monitor(interval):
    print(f"Starting monitor with {interval}s interval. Press Ctrl+C to stop.")
    
    try:
        while True:
            get_status_report(interval)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
        sys.exit(0)
