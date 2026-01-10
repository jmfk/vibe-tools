import datetime
from typing import Optional

import click

from vibe_tools.issues import Issue, load_all_issues, load_issue_by_id, save_issue
from vibe_tools.ralph import issue_solve_loop


def _solve_issue(issue: Issue, mode: str, agent: str, stream: bool = False):
    """Internal helper to solve a single issue."""
    click.echo(f"🎯 Starting {mode} mode for issue: {issue.title} ({issue.id})")

    from vibe_tools.commands.sync import sync_issues
    # Update status if not already in progress
    now = datetime.datetime.now().isoformat()
    if issue.status == "backlog":
        issue.status = "in_progress"
        issue.updated_at = now
        save_issue(issue)
        sync_issues(quiet=True)
        click.echo(f"Status transitioned to: {issue.status}")

    # In local-first workflow, we want to update the investigation or solution notes
    note = f"- Agent started {mode} mode at {now}"
    if mode == "investigate":
        issue.body.investigation_notes = (issue.body.investigation_notes + "\n" + note).strip()
    else:
        issue.body.solution_notes = (issue.body.solution_notes + "\n" + note).strip()

    issue.updated_at = now
    save_issue(issue)
    sync_issues(quiet=True)

    if mode == "solve":
        success = issue_solve_loop(issue, agent, stream=stream)
        if success:
            click.echo(click.style(f"✅ Issue {issue.id} solved successfully!", fg="green"))
        else:
            click.echo(click.style(f"❌ Failed to solve issue {issue.id}. Check failure report in issues/fails/", fg="red"))
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
            issue = load_issue_by_id(issue_id)
            if not issue:
                click.echo(f"Error: Issue {issue_id} not found.")
                return
            _solve_issue(issue, mode, agent, stream)
        elif solve_next:
            issues = [i for i in load_all_issues() if i.status in ("backlog", "in_progress")]
            if not issues:
                click.echo("No issues in backlog or in progress.")
                return
            _solve_issue(issues[0], mode, agent, stream)
        elif solve_all:
            issues = [i for i in load_all_issues() if i.status in ("backlog", "in_progress")]
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
