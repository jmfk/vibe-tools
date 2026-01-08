import click

from vibe_tools.utils import get_agent_processes


def register_ps(cli):
    @click.command()
    def ps():
        """List active agent processes."""
        processes = get_agent_processes()
        if not processes:
            click.echo("No active agent processes found.")
            return

        click.echo(f"{'PID':<10} {'TARGET':<20} {'COMMAND'}")
        click.echo("-" * 60)
        for p in processes:
            click.echo(f"{p['pid']:<10} {p['target']:<20} {p['command']}")
    cli.add_command(ps)
