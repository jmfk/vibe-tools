import click

from vibe_tools.utils import get_vibe_status_report


def register_status(cli):
    @click.command()
    def status():
        """Display a comprehensive system status report."""
        click.echo(get_vibe_status_report())
    cli.add_command(status)
