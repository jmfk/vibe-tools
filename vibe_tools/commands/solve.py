import click
import datetime
from typing import Optional
from vibe_tools.issues import load_issue_by_id, save_issue, Issue
from vibe_tools.utils import logger

def append_to_section(body: str, section_title: str, text: str) -> str:
    """Helper to append text to a specific markdown section."""
    marker = f"## {section_title}"
    if marker not in body:
        return body + f"\n\n{marker}\n{text}"
    
    parts = body.split(marker)
    # parts[0] is everything before section
    # parts[1] is everything after section title
    
    # We want to insert after the section title but before the next section
    subparts = parts[1].split("\n## ")
    subparts[0] = subparts[0].rstrip() + f"\n{text}\n"
    
    new_parts1 = "\n## ".join(subparts)
    return parts[0] + marker + new_parts1

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
            issue.body = append_to_section(issue.body, "Investigation Notes", note)
        else:
            issue.body = append_to_section(issue.body, "Solution Notes", note)
            
        issue.updated_at = now
        save_issue(issue)
        
        # Here we would normally invoke Ralph or another agent loop
        # For this implementation, we ensure the issue state is correctly set up.
        
        click.echo(f"Issue {issue_id} updated and marked as in_progress.")
        click.echo("Agent can now proceed with implementation/investigation based on the issue file.")

    cli.add_command(solve_command)
