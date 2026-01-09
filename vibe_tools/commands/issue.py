import click

def register_issue(cli):
    @click.group(name="issue")
    def issue_group():
        """Local-first issue management with GitHub sync."""
        pass

    from vibe_tools.commands.sync import register_sync
    from vibe_tools.commands.investigate import register_investigate
    from vibe_tools.commands.solve import register_solve

    # We need to adapt the register functions to work with a group
    # or just manually add the commands here.
    
    # For now, let's just use the existing ones but pass the group instead of the main cli
    register_sync(issue_group)
    register_investigate(issue_group)
    register_solve(issue_group)

    cli.add_command(issue_group)
