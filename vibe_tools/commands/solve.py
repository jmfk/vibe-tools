import click
import datetime
from typing import Optional, List
from vibe_tools.issues import load_issue_by_id, save_issue, Issue, load_all_issues
from vibe_tools.utils import logger

def _solve_issue(issue: Issue, mode: str):
    """Internal helper to solve a single issue."""
    click.echo(f"🎯 Starting {mode} mode for issue: {issue.title} ({issue.id})")
    
    # Update status if not already in progress
    now = datetime.datetime.now().isoformat()
    if issue.status == "backlog":
        issue.status = "in_progress"
        issue.updated_at = now
        save_issue(issue)
        click.echo(f"Status transitioned to: {issue.status}")

    # In local-first workflow, we want to update the investigation or solution notes
    note = f"- Agent started {mode} mode at {now}"
    if mode == "investigate":
        issue.body.investigation_notes = (issue.body.investigation_notes + "\n" + note).strip()
    else:
        issue.body.solution_notes = (issue.body.solution_notes + "\n" + note).strip()
        
    issue.updated_at = now
    save_issue(issue)
    
    # Here we would normally invoke Ralph or another agent loop
    # For this implementation, we ensure the issue state is correctly set up.
    
    click.echo(f"Issue {issue.id} updated and marked as in_progress.")
    click.echo("Agent can now proceed with implementation/investigation based on the issue file.")

def register_solve(cli):
    @click.command(name="solve")
    @click.argument("issue_id", required=False)
    @click.option("--next", "solve_next", is_flag=True, help="Solve the next issue in the backlog")
    @click.option("--all", "solve_all", is_flag=True, help="Iterate through all backlog issues and solve them")
    @click.option("--mode", type=click.Choice(["investigate", "solve"]), default="solve")
    @click.pass_context
    def solve_command(ctx, issue_id: Optional[str], solve_next: bool, solve_all: bool, mode: str):
        """Resolve issue(s) via agent-driven loop."""
        if issue_id:
            issue = load_issue_by_id(issue_id)
            if not issue:
                click.echo(f"Error: Issue {issue_id} not found.")
                return
            _solve_issue(issue, mode)
        elif solve_next:
            issues = [i for i in load_all_issues() if i.status == "backlog"]
            if not issues:
                click.echo("No issues in backlog.")
                return
            _solve_issue(issues[0], mode)
        elif solve_all:
            issues = [i for i in load_all_issues() if i.status == "backlog"]
            if not issues:
                click.echo("No issues in backlog.")
                return
            click.echo(f"Solving {len(issues)} issues...")
            for issue in issues:
                _solve_issue(issue, mode)
                click.echo("-" * 40)
        else:
            click.echo("Error: Please provide an issue_id, --next, or --all.")
            click.echo(ctx.get_help())

    cli.add_command(solve_command)
