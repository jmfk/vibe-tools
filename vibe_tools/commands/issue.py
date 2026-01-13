import click


def register_issue(cli):
    @click.group(name="issue")
    def issue_group():
        """Local-first issue management with GitHub sync."""
        pass

    from vibe_tools.commands.investigate import register_investigate
    from vibe_tools.commands.issue_add import register_issue_add
    from vibe_tools.commands.issue_list import register_issue_list
    from vibe_tools.commands.solve import register_solve, load_prd_by_id

    register_issue_list(issue_group)
    register_issue_add(issue_group)

    @issue_group.command(name="close")
    @click.argument("issue_id")
    def close_issue(issue_id):
        """Close a local issue and mark for sync."""
        issue = load_prd_by_id(issue_id)
        if not issue:
            click.echo(f"Error: Issue {issue_id} not found.")
            return

        import datetime
        issue.status = "done"
        issue.updated_at = datetime.datetime.now().isoformat()
        
        # Move to history
        from vibe_tools.utils import PRODUCT_HISTORY_DIR
        new_path = PRODUCT_HISTORY_DIR / issue.path.name
        issue.save(new_path)
        if issue.path.exists():
            issue.path.unlink()
        
        click.echo(f"Issue {issue_id} marked as done and moved to history.")
        click.echo("Run 'vibe sync' to update GitHub.")

    register_investigate(issue_group)
    register_solve(issue_group)

    cli.add_command(issue_group)
