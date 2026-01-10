import click
import datetime
import json
from vibe_tools.issues import Issue, IssueBody, save_issue, generate_issue_id
from vibe_tools.utils import run_llm, get_prompt

def register_issue_add(issue_group):
    @issue_group.command(name="add")
    @click.argument("prompt", required=True)
    @click.option("--title", help="Explicitly set title")
    @click.option("--severity", type=click.Choice(["low", "medium", "high", "critical"]), help="Explicitly set severity")
    @click.option("--service", help="Explicitly set service")
    def add_issue(prompt, title, severity, service):
        """Create a new local issue from a prompt."""
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
            created_at=now,
            updated_at=now,
            body=IssueBody(summary=issue_summary),
        )
        
        save_issue(issue)
        
        click.echo(f"✅ Issue created successfully!")
        click.echo(f"ID:       {issue.id}")
        click.echo(f"Title:    {issue.title}")
        click.echo(f"Location: issues/backlog/{issue.id}.md")
