import click
import re
from typing import Optional
from vibe_tools.issues import load_all_issues

def list_issues_impl(status, severity, service, search, full, search_query):
    """Internal implementation of issue listing."""
    issues = load_all_issues()
    
    # Merge search and search_query
    effective_search = search or search_query
    
    filtered_issues = []
    for issue in issues:
        if status:
            if issue.status != status:
                continue
        elif issue.status == "done":
            # Hide done issues by default unless specifically filtered
            continue
            
        if severity and issue.severity != severity:
            continue
        if service and service.lower() not in (issue.service or "").lower():
            continue
        
        if effective_search:
            pattern = re.compile(effective_search, re.IGNORECASE)
            match_title = pattern.search(issue.title)
            match_body = pattern.search(issue.body.to_markdown())
            match_status = pattern.search(issue.status)
            if not (match_title or match_body or match_status):
                continue
        
        filtered_issues.append(issue)
    
    if not filtered_issues:
        click.echo("No matching issues found.")
        return

    if full:
        for issue in filtered_issues:
            click.echo("=" * 40)
            click.echo(f"ID:       {issue.id}")
            click.echo(f"Title:    {issue.title}")
            click.echo(f"Status:   {issue.status}")
            click.echo(f"Severity: {issue.severity}")
            click.echo(f"Service:  {issue.service or 'N/A'}")
            click.echo("-" * 40)
            click.echo(issue.body.to_markdown())
            click.echo("")
    else:
        # Table View
        header = f"{'ID':<25} {'Status':<12} {'Severity':<10} {'Service':<15} {'Title'}"
        click.echo(header)
        click.echo("-" * len(header))
        for issue in filtered_issues:
            service_str = issue.service or "N/A"
            click.echo(f"{issue.id:<25} {issue.status:<12} {issue.severity:<10} {service_str:<15} {issue.title}")

def register_issue_list(issue_group):
    options = [
        click.option("--status", type=click.Choice(["backlog", "in_progress", "blocked", "done"]), help="Filter by status"),
        click.option("--severity", type=click.Choice(["low", "medium", "high", "critical"]), help="Filter by severity"),
        click.option("--service", help="Filter by service name"),
        click.option("--search", "-s", help="Search title or body content (regex support)"),
        click.option("--full", "-v", is_flag=True, help="Display detailed view"),
        click.argument("search_query", required=False)
    ]
    
    def add_options(f):
        for option in reversed(options):
            f = option(f)
        return f

    @issue_group.command(name="list")
    @add_options
    def list_issues(**kwargs):
        """List and filter local issues."""
        list_issues_impl(**kwargs)

    @issue_group.command(name="ls")
    @add_options
    def ls_issues(**kwargs):
        """Alias for 'vibe issue list'."""
        list_issues_impl(**kwargs)
