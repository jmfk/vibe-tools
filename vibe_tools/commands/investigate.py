import click
import datetime
import os
import pathlib
import json
from typing import List, Optional
from vibe_tools.issues import Issue, save_issue, generate_issue_id
from vibe_tools.utils import LOGS_DIR, logger

def get_log_files() -> List[pathlib.Path]:
    if not LOGS_DIR.exists():
        return []
    return sorted(list(LOGS_DIR.glob("*.log")), key=lambda p: p.stat().st_mtime, reverse=True)

def register_investigate(cli):
    @click.command(name="investigate")
    @click.option("--logs", help="Path to logs to investigate")
    @click.option("--service", help="Service name")
    def investigate_command(logs, service):
        """Create issues via guided investigation."""
        click.echo("🚀 Starting guided investigation...")
        
        log_files = []
        if logs:
            log_files = [pathlib.Path(logs)]
        else:
            log_files = get_log_files()
        
        evidence = ""
        if log_files:
            click.echo(f"Found {len(log_files)} log files. Analyzing latest: {log_files[0].name}")
            content = log_files[0].read_text().splitlines()[-20:]
            click.echo("\nLatest log snippets:")
            for line in content:
                click.echo(f"  {line}")
                evidence += f"  {line}\n"

        title = click.prompt("\nIssue Title")
        severity = click.prompt("Severity", type=click.Choice(["low", "medium", "high", "critical"]), default="medium")
        service = service or click.prompt("Service", default="core")
        
        summary = click.prompt("Summary (Markdown supported)")
        reproduction = click.prompt("Reproduction Steps", default="N/A")
        expected = click.prompt("Expected Behavior", default="N/A")
        actual = click.prompt("Actual Behavior", default="N/A")
        acceptance = click.prompt("Acceptance Criteria", default="Fix the issue.")

        body = f"""## Summary
{summary}

## Reproduction Steps
{reproduction}

## Expected Behavior
{expected}

## Actual Behavior
{actual}

## Evidence
```
{evidence}
```

## Acceptance Criteria
{acceptance}

## Investigation Notes
- Created via `vibe investigate` on {datetime.datetime.now().isoformat()}

## Solution Notes
(TBD)
"""

        issue_id = generate_issue_id()
        now = datetime.datetime.now().isoformat()
        
        issue = Issue(
            id=issue_id,
            title=title,
            status="backlog",
            severity=severity,
            service=service,
            created_at=now,
            updated_at=now,
            body=body
        )
        
        save_issue(issue)
        click.echo(f"\n✅ Issue created: {issue_id}")
        click.echo(f"Location: issues/backlog/{issue_id}.md")
        
        if click.confirm("Sync to GitHub now?"):
            from vibe_tools.commands.sync import get_github_repo, push_local_issues
            repo = get_github_repo()
            if repo:
                push_local_issues(repo)
                click.echo("Synced to GitHub.")
            else:
                click.echo("Failed to sync: Not a GitHub repository.")
                
    cli.add_command(investigate_command)
    cli.add_command(investigate_command, name="inv")
