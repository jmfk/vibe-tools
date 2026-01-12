import datetime
import sys
import time

from vibe_tools.cost import AGENT_DEFAULT_MODEL, CostLogger
from vibe_tools.utils import get_agent_command, get_prompt, run_agent, run_command


def get_status_report(agent, interval, cost_logger=None, stream=False):
    """Gathers context and calls agent to inspect progress."""
    # Check if we are in a git repository
    stdout, code = run_command(["git", "rev-parse", "--is-inside-work-tree"], check=False)
    if code != 0:
        print("Error: Not in a git repository. Status report requires a git project.")
        return

    current_branch_out, _ = run_command(["git", "branch", "--show-current"], check=False)
    git_status_out, _ = run_command(["git", "status", "--short"], check=False)
    last_diff_out, _ = run_command(["git", "diff", "HEAD", "vibe_tools/"], check=False)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        prompt_base = get_prompt("monitor_prompt.txt")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please run 'vibe init' to initialize the project.")
        return

    inspection_prompt = prompt_base.format(
        timestamp=timestamp,
        current_branch=current_branch_out,
        git_status=git_status_out,
        last_diff=last_diff_out[:2000],
    )

    cmd = get_agent_command(agent, inspection_prompt)

    print(f"\n--- Monitoring Report [{timestamp}] ---")
    output, returncode = run_agent(cmd, stream=stream)

    if cost_logger:
        cost_logger.log_run(
            agent=agent,
            model=AGENT_DEFAULT_MODEL.get(agent, "unknown"),
            prompt=inspection_prompt,
            output=output,
            prd_name="N/A",
            iteration=1,
            phase="monitor",
            purpose="monitoring_progress",
        )

    if returncode == 0:
        print(output)
    else:
        print(f"Error calling agent (Exit Code {returncode}): {output}")


def run_monitor(agent, interval, stream=False):
    from vibe_tools.cli import load_config

    print(f"Starting monitor with {interval}s interval using agent {agent}. Press Ctrl+C to stop.")

    config = load_config()
    cost_logger = CostLogger(config)

    try:
        while True:
            get_status_report(agent, interval, cost_logger=cost_logger, stream=stream)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
        sys.exit(0)
