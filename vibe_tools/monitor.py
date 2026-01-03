import time
import datetime
import sys
import pathlib
import click
from vibe_tools.utils import run_command, run_agent, get_agent_command

PROMPTS_DIR = pathlib.Path("prompts")
MONITOR_PROMPT_TEMPLATE = PROMPTS_DIR / "monitor_prompt.txt"

def get_status_report(agent, interval):
    """Gathers context and calls agent to inspect progress."""
    # Check if we are in a git repository
    stdout, code = run_command(["git", "rev-parse", "--is-inside-work-tree"], check=False)
    if code != 0:
        print("Error: Not in a git repository. Status report requires a git project.")
        return

    current_branch_out, _ = run_command(["git", "branch", "--show-current"], check=False)
    git_status_out, _ = run_command(["git", "status", "--short"], check=False)
    last_diff_out, _ = run_command(["git", "diff", "HEAD", "src/"], check=False)
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not MONITOR_PROMPT_TEMPLATE.exists():
        print(f"Error: prompts/ directory not found or monitor_prompt.txt is missing.")
        print("Please run 'vibe init' to initialize the project.")
        return

    prompt_base = MONITOR_PROMPT_TEMPLATE.read_text()
    inspection_prompt = prompt_base.format(
        timestamp=timestamp,
        current_branch=current_branch_out,
        git_status=git_status_out,
        last_diff=last_diff_out[:2000]
    )

    cmd = get_agent_command(agent, inspection_prompt)
    
    print(f"\n--- Monitoring Report [{timestamp}] ---")
    output, returncode = run_agent(cmd)
    if returncode == 0:
        print(output)
    else:
        print(f"Error calling agent (Exit Code {returncode}): {output}")

def run_monitor(agent, interval):
    print(f"Starting monitor with {interval}s interval using agent {agent}. Press Ctrl+C to stop.")
    
    try:
        while True:
            get_status_report(agent, interval)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
        sys.exit(0)
