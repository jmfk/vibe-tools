import datetime
import pathlib
import re
from typing import List

import click

from vibe_tools.prds import PRD, generate_prd_id
from vibe_tools.utils import LOGS_DIR, logger


def get_log_files() -> List[pathlib.Path]:
    if not LOGS_DIR.exists():
        return []
    return sorted(
        list(LOGS_DIR.glob("*.log")), key=lambda p: p.stat().st_mtime, reverse=True
    )


def redact_content(content: str) -> str:
    """Simple redaction for common secrets."""
    # Redact common secret patterns
    patterns = [
        (
            r'(?i)(api_key|password|token|secret|key|auth|credential)["\']?\s*[:=]\s*["\']?([^"\'\s,;}]+)["\']?',
            r"\1: [REDACTED]",
        ),
        (r'(?i)(bearer|token)\s+([^"\'\s,;}]+)', r"\1 [REDACTED]"),
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
            click.echo(
                f"Found {len(log_files)} log files. Analyzing latest: {log_files[0].name}"
            )
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
        severity = click.prompt(
            "Severity",
            type=click.Choice(["low", "medium", "high", "critical"]),
            default="medium",
        )
        service = service or click.prompt("Service", default="core")

        summary = click.prompt("Summary (Markdown supported)")
        if clustered and not summary:
            summary = "Potential errors detected:\n" + "\n".join(
                [f"- {c}" for c in clustered]
            )

        reproduction = click.prompt("Reproduction Steps", default="N/A")
        expected = click.prompt("Expected Behavior", default="N/A")
        actual = click.prompt("Actual Behavior", default="N/A")
        acceptance = click.prompt("Acceptance Criteria", default="Fix the issue.")

        from vibe_tools.utils import PRODUCT_DIR, PLANNING_INBOX_DIR

        issue_id = generate_prd_id(PRODUCT_DIR)
        now = datetime.datetime.now().isoformat()

        # Create sanitized filename
        safe_title = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        filename = f"{issue_id}-{safe_title}.md"
        if len(filename) > 64:
            filename = filename[:60] + ".md"

        target_path = PLANNING_INBOX_DIR / filename

        content = f"# {title}\n\n"
        if summary:
            content += f"## Summary\n{summary}\n\n"
        if reproduction:
            content += f"## Reproduction Steps\n{reproduction}\n\n"
        if expected:
            content += f"## Expected Behavior\n{expected}\n\n"
        if actual:
            content += f"## Actual Behavior\n{actual}\n\n"
        if evidence:
            content += f"## Evidence\n```\n{evidence}\n```\n\n"
        if acceptance:
            content += f"## Acceptance Criteria\n{acceptance}\n\n"

        content += (
            f"## Investigation Notes\n- Created via `vibe investigate` on {now}\n"
        )

        prd = PRD(
            id=issue_id,
            title=title,
            type="ISSUE",
            status="backlog",
            created_at=now,
            updated_at=now,
            content=content,
            metadata={
                "severity": severity,
                "service": service,
                "summary": summary,
                "reproduction_steps": reproduction,
                "expected_behavior": expected,
                "actual_behavior": actual,
                "acceptance_criteria": acceptance,
            },
            path=target_path,
        )

        prd.save()
        click.echo(f"\n✅ Issue created: {issue_id}")
        click.echo(f"Location: {target_path}")

        if github or click.confirm("Sync to GitHub now?"):
            # The sync command is a bit different now, it's a CLI command.
            # For now, let's just advise the user to run 'vibe sync'.
            click.echo("Please run 'vibe sync' to synchronize with GitHub.")

    cli.add_command(investigate_command)
    cli.add_command(investigate_command, name="inv")
