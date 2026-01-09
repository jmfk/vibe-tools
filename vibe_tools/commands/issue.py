import click

def register_issue(cli):
    @click.group(name="issue")
    def issue_group():
        """Local-first issue management with GitHub sync."""
        pass

    from vibe_tools.commands.sync import register_sync
    from vibe_tools.commands.investigate import register_investigate
    from vibe_tools.commands.solve import register_solve
    from vibe_tools.issues import load_index, load_issue_by_id, save_issue

    @issue_group.command(name="list")
    def list_issues():
        """List all local issues."""
        index = load_index()
        if not index:
            click.echo("No local issues found.")
            return
        
        click.echo(f"{'ID':<20} {'Status':<15} {'Severity':<10} {'Title'}")
        click.echo("-" * 70)
        for issue_id in sorted(index.keys()):
            issue = load_issue_by_id(issue_id)
            if issue:
                click.echo(f"{issue.id:<20} {issue.status:<15} {issue.severity:<10} {issue.title}")

    @issue_group.command(name="close")
    @click.argument("issue_id")
    def close_issue(issue_id):
        """Close a local issue and mark for sync."""
        issue = load_issue_by_id(issue_id)
        if not issue:
            click.echo(f"Error: Issue {issue_id} not found.")
            return
        
        import datetime
        issue.status = "done"
        issue.updated_at = datetime.datetime.now().isoformat()
        save_issue(issue)
        click.echo(f"Issue {issue_id} marked as done. Run 'vibe issue sync' to close on GitHub.")

    register_sync(issue_group)
    register_investigate(issue_group)
    register_solve(issue_group)

    cli.add_command(issue_group)
