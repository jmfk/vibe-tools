import click
import datetime
from typing import Optional
from vibe_tools.issues import load_issue_by_id, save_issue, Issue
from vibe_tools.utils import logger

def register_solve(cli):
    @click.command(name="solve")
    @click.argument("issue_id")
    @click.option("--mode", type=click.Choice(["investigate", "solve"]), default="solve")
    @click.pass_context
    def solve_command(ctx, issue_id: str, mode: str):
        """Resolve issue via agent-driven loop."""
        issue = load_issue_by_id(issue_id)
        if not issue:
            click.echo(f"Error: Issue {issue_id} not found.")
            return

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
        
        click.echo(f"Issue {issue_id} updated and marked as in_progress.")
        click.echo("Agent can now proceed with implementation/investigation based on the issue file.")

    cli.add_command(solve_command)
