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
        if issue.status == "backlog":
            issue.status = "in_progress"
            issue.updated_at = datetime.datetime.now().isoformat()
            save_issue(issue)
            click.echo(f"Status transitioned to: {issue.status}")

        from vibe_tools.ralph import implementation_loop
        
        # In a real implementation, we would pass the issue context to the agent loop
        # For now, we'll simulate the loop call or tell the agent (if the user is an agent) 
        # what to do based on the issue.
        
        agent = ctx.obj.get("agent", "cursor-agent")
        stream = ctx.obj.get("stream", False)
        
        # Add issue context to Ralph or whatever engine we use
        click.echo(f"Using agent: {agent}")
        
        if mode == "investigate":
            click.echo("Running investigation loop...")
            # Simulate investigation
            issue.body += f"\n- Investigation started by agent at {datetime.datetime.now().isoformat()}"
        else:
            click.echo("Running solve loop...")
            # Simulate solve
            # success = implementation_loop(agent, stream=stream, context=issue.to_markdown())
            issue.body += f"\n- Solve started by agent at {datetime.datetime.now().isoformat()}"

        issue.updated_at = datetime.datetime.now().isoformat()
        save_issue(issue)
        
        click.echo(f"Issue {issue_id} updated. Please proceed with implementation/investigation.")

    cli.add_command(solve_command)
