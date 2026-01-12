import datetime
import json

import click

from vibe_tools.issues import BACKLOG_DIR, Issue, IssueBody, generate_issue_id, save_issue
from vibe_tools.utils import get_prompt, run_llm


def get_interactive_prompt():
    from prompt_toolkit import PromptSession
    from prompt_toolkit.key_binding import KeyBindings

    kb = KeyBindings()

    @kb.add("c-s")
    @kb.add("c-a")
    def _(event):
        event.app.exit(result=event.app.current_buffer.text)

    @kb.add("c-q")
    def _(event):
        event.app.exit(result=None)

    session = PromptSession(key_bindings=kb)

    click.echo(click.style("Enter issue prompt (Ctrl-S or Ctrl-A to save, Ctrl-Q to quit):", fg="cyan"))
    click.echo(click.style("-" * 60, fg="bright_black"))

    result = session.prompt(multiline=True)
    return result

def register_issue_add(issue_group):
    @issue_group.command(name="add")
    @click.argument("prompt", required=False)
    @click.option("--title", help="Explicitly set title")
    @click.option("--severity", type=click.Choice(["low", "medium", "high", "critical"]), help="Explicitly set severity")
    @click.option("--service", help="Explicitly set service")
    def add_issue(prompt, title, severity, service):
        """Create a new local issue from a prompt."""
        if not prompt:
            prompt = get_interactive_prompt()
            if not prompt:
                click.echo("Aborted.")
                return

        click.echo("🤖 Analyzing prompt and generating issue details...")

        template_str = get_prompt("issue_add_prompt.txt")
        rendered_prompt = template_str.replace("{{ prompt }}", prompt)

        response = run_llm(rendered_prompt)

        # Parse JSON from response
        try:
            # Simple JSON extraction in case there's markdown
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "{" in response:
                json_str = response[response.find("{"):response.rfind("}")+1]
            else:
                json_str = response

            data = json.loads(json_str)
        except Exception as e:
            click.echo(f"Error parsing AI response: {e}")
            click.echo(f"Raw response: {response}")
            return

        # Apply overrides
        issue_title = title or data.get("title", "Untitled Issue")
        issue_severity = severity or data.get("severity", "medium")
        issue_service = service or data.get("service", "")
        issue_summary = data.get("summary", "")

        now = datetime.datetime.now().isoformat()
        issue_id = generate_issue_id()

        issue = Issue(
            id=issue_id,
            title=issue_title,
            status="backlog",
            severity=issue_severity,
            service=issue_service,
            summary=issue_summary,
            created_at=now,
            updated_at=now,
            body=IssueBody(summary=issue_summary),
        )

        save_issue(issue)

        from vibe_tools.commands.sync import sync_issues
        sync_issues(quiet=True)

        click.echo("✅ Issue created successfully!")
        click.echo(f"ID:       {issue.id}")
        click.echo(f"Title:    {issue.title}")
        click.echo(f"Location: {BACKLOG_DIR}/{issue.id}.md")

    issue_group.add_command(add_issue)
