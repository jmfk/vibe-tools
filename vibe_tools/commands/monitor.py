import click
from vibe_tools.utils import get_agent_processes, cleanup_stale_processes


@click.command()
@click.option("--clean", is_flag=True, help="Clean up stale agent processes.")
def monitor(clean):
    """Real-time monitoring of active agents and processes."""
    if clean:
        click.echo("Cleaning up stale agent processes...")
        cleaned = cleanup_stale_processes()
        if cleaned:
            for msg in cleaned:
                click.echo(f"  {msg}")
        else:
            click.echo("No stale processes found.")
        return

    processes = get_agent_processes()
    if not processes:
        click.echo("No active agent processes found.")
        return

    click.echo(f"Active agent processes ({len(processes)}):")
    for proc in processes:
        pid = proc.get("pid", "unknown")
        name = proc.get("name", "unknown")
        status = proc.get("status", "unknown")
        click.echo(f"  - [{pid}] {name} ({status})")


def register_monitor(cli):
    cli.add_command(monitor)
