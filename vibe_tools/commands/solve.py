import datetime
from typing import Optional, List

import click

from vibe_tools.prds import PRD, load_prd
from vibe_tools.ralph import implementation_loop


def load_prd_by_id(prd_id: str) -> Optional[PRD]:
    from vibe_tools.utils import PRODUCT_DIR
    if not PRODUCT_DIR.exists():
        return None
    for f in PRODUCT_DIR.rglob("*.md"):
        if prd_id.upper() in f.name.upper():
            try:
                return load_prd(f)
            except Exception:
                continue
    return None

def load_all_issue_prds() -> List[PRD]:
    from vibe_tools.utils import PRODUCT_DIR
    prds = []
    if PRODUCT_DIR.exists():
        for f in PRODUCT_DIR.rglob("*.md"):
            try:
                p = load_prd(f)
                if p.type == "ISSUE":
                    prds.append(p)
            except Exception:
                continue
    return sorted(prds, key=lambda x: x.id)

def _solve_issue(issue: PRD, mode: str, agent: str, stream: bool = False):
    """Internal helper to solve a single issue."""
    from vibe_tools.utils import PRODUCT_IN_PROGRESS_DIR
    click.echo(f"🎯 Starting {mode} mode for issue: {issue.title} ({issue.id})")

    # Update status if not already in progress
    if issue.status == "backlog":
        issue.status = "in_progress"
        # Move to in_progress directory if it's not already there
        if "in_progress" not in str(issue.path):
            new_path = PRODUCT_IN_PROGRESS_DIR / issue.path.name
            issue.save(new_path)
            issue.path.unlink()
            issue.path = new_path
        else:
            issue.save()
        click.echo(f"Status transitioned to: {issue.status}")

    # In local-first workflow, we want to update the history
    issue.append_history(f"Agent started {mode} mode.")
    issue.save()

    if mode == "solve":
        # Redirect to the unified implementation loop
        success = implementation_loop(agent, stream=stream)
        if success:
            click.echo(click.style(f"✅ Issue {issue.id} solved successfully!", fg="green"))
        else:
            click.echo(click.style(f"❌ Failed to solve issue {issue.id}.", fg="red"))
    else:
        click.echo(f"Issue {issue.id} updated and marked as in_progress.")
        click.echo("Investigation mode currently updates the issue state.")

def register_solve(cli):
    @click.command(name="solve")
    @click.argument("issue_id", required=False)
    @click.option("--next", "solve_next", is_flag=True, help="Solve the next issue in the backlog")
    @click.option("--all", "solve_all", is_flag=True, help="Iterate through all backlog issues and solve them")
    @click.option("--mode", type=click.Choice(["investigate", "solve"]), default="solve")
    @click.option("--agent", default="cursor-agent", help="Agent to use (cursor-agent, claude, antigravity)")
    @click.option("--stream", is_flag=True, help="Stream agent output to console")
    @click.pass_context
    def solve_command(ctx, issue_id: Optional[str], solve_next: bool, solve_all: bool, mode: str, agent: str, stream: bool):
        """Resolve issue(s) via agent-driven loop."""
        if issue_id:
            issue = load_prd_by_id(issue_id)
            if not issue:
                click.echo(f"Error: Issue {issue_id} not found.")
                return
            _solve_issue(issue, mode, agent, stream)
        elif solve_next:
            issues = [i for i in load_all_issue_prds() if i.status in ("backlog", "in_progress")]
            if not issues:
                click.echo("No issues in backlog or in progress.")
                return
            _solve_issue(issues[0], mode, agent, stream)
        elif solve_all:
            issues = [i for i in load_all_issue_prds() if i.status in ("backlog", "in_progress")]
            if not issues:
                click.echo("No issues in backlog or in progress.")
                return
            click.echo(f"Solving {len(issues)} issues...")
            for issue in issues:
                _solve_issue(issue, mode, agent, stream)
                click.echo("-" * 40)
        else:
            click.echo("Error: Please provide an issue_id, --next, or --all.")
            click.echo(ctx.get_help())

    cli.add_command(solve_command)
