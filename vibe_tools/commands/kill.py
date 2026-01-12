import click

from vibe_tools.utils import cleanup_stale_processes, get_agent_processes


def register_kill(cli):
    @click.command()
    @click.option("--yes", "-y", is_flag=True, help="Automatically confirm kill.")
    def kill(yes):
        """Kill all active agent processes."""
        processes = get_agent_processes()
        if not processes:
            click.echo("No active agent processes found.")
            return

        if not yes:
            click.echo("Active agent processes:")
            for p in processes:
                click.echo(f"  - {p['pid']}: {p['command']}")

            if not click.confirm(
                "\nAre you sure you want to kill all these processes?", default=False
            ):
                click.echo("Aborted.")
                return

        killed = cleanup_stale_processes()
        if killed:
            click.echo(f"✅ Killed processes for: {', '.join(killed)}")
        else:
            click.echo("No processes were killed.")

    cli.add_command(kill)
