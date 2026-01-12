import click

from vibe_tools.branches import display_branches_table


def register_branches(cli):
    @click.command()
    @click.pass_context
    def branches(ctx):
        """List all local branches and their dependencies."""
        display_branches_table()

    cli.add_command(branches)
