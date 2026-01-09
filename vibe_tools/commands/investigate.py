import click
import datetime
import os
import pathlib
import json
import re
from typing import List, Optional
from vibe_tools.issues import Issue, IssueBody, save_issue, generate_issue_id
from vibe_tools.utils import LOGS_DIR, logger

def get_log_files() -> List[pathlib.Path]:
    if not LOGS_DIR.exists():
        return []
    return sorted(list(LOGS_DIR.glob("*.log")), key=lambda p: p.stat().st_mtime, reverse=True)

def redact_content(content: str) -> str:
    """Simple redaction for common secrets."""
    # Redact common secret patterns
    patterns = [
        (r'(?i)(api_key|password|token|secret|key|auth|credential)["\']?\s*[:=]\s*["\']?([^"\'\s,;}]+)["\']?', r'\1: [REDACTED]'),
        (r'(?i)(bearer|token)\s+([^"\'\s,;}]+)', r'\1 [REDACTED]'),
    ]
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)
    return content

def cluster_errors(lines: List[str]) -> List[str]:
    """Very basic clustering of error lines."""
    clusters = {}
    for line in lines:
        # Look for things that look like errors
        if "ERROR" in line or "Exception" in line or "Error:" in line:
            # Strip timestamps or common prefixes to cluster
            # This is a very simple heuristic
            key = line
            if " - " in line:
                key = line.split(" - ", 1)[-1]
            clusters[key] = clusters.get(key, 0) + 1
    
    # Sort by frequency
    sorted_clusters = sorted(clusters.items(), key=lambda x: x[1], reverse=True)
    return [f"({count}x) {text}" for text, count in sorted_clusters[:5]]

def register_investigate(cli):
    @click.command(name="investigate")
    @click.option("--logs", help="Path to logs to investigate")
    @click.option("--service", help="Service name")
    @click.option("--github", is_flag=True, help="Create GitHub issue immediately")
    def investigate_command(logs, service, github):
        """Create issues via guided investigation."""
        click.echo("🚀 Starting guided investigation...")
        
        log_files = []
        if logs:
            log_files = [pathlib.Path(logs)]
        else:
            log_files = get_log_files()
        
        evidence = ""
        clustered = []
        if log_files:
            click.echo(f"Found {len(log_files)} log files. Analyzing latest: {log_files[0].name}")
            try:
                all_lines = log_files[0].read_text().splitlines()
                content = all_lines[-100:]
                click.echo("\nLatest log snippets (redacted):")
                for line in content[-20:]:
                    redacted_line = redact_content(line)
                    click.echo(f"  {redacted_line}")
                    evidence += f"{redacted_line}\n"
                
                clustered = cluster_errors(all_lines[-500:])
                if clustered:
                    click.echo("\nPotential error clusters found:")
                    for c in clustered:
                        click.echo(f"  {c}")
            except Exception as e:
                logger.error(f"Failed to read logs: {e}")

        title = click.prompt("\nIssue Title")
        severity = click.prompt("Severity", type=click.Choice(["low", "medium", "high", "critical"]), default="medium")
        service = service or click.prompt("Service", default="core")
        
        summary = click.prompt("Summary (Markdown supported)")
        if clustered and not summary:
            summary = "Potential errors detected:\n" + "\n".join([f"- {c}" for c in clustered])
            
        reproduction = click.prompt("Reproduction Steps", default="N/A")
        expected = click.prompt("Expected Behavior", default="N/A")
        actual = click.prompt("Actual Behavior", default="N/A")
        acceptance = click.prompt("Acceptance Criteria", default="Fix the issue.")

        body = IssueBody(
            summary=summary,
            reproduction_steps=reproduction,
            expected_behavior=expected,
            actual_behavior=actual,
            evidence=f"```\n{evidence}\n```" if evidence else "N/A",
            acceptance_criteria=acceptance,
            investigation_notes=f"- Created via `vibe investigate` on {datetime.datetime.now().isoformat()}"
        )

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
        
        if github or click.confirm("Sync to GitHub now?"):
            from vibe_tools.commands.sync import get_github_repo, push_local_issues
            repo = get_github_repo()
            if repo:
                push_local_issues(repo)
                click.echo("Synced to GitHub.")
            else:
                click.echo("Failed to sync: Not a GitHub repository.")
                
    cli.add_command(investigate_command)
    cli.add_command(investigate_command, name="inv")
