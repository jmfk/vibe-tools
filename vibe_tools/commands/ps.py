import click

from vibe_tools.utils import get_agent_processes


def register_ps(cli):
    @click.command()
    @click.option("--json", "json_format", is_flag=True, help="Output in JSON format.")
    def ps(json_format):
        """List active agent processes."""
        processes = get_agent_processes()
        if json_format:
            import json
            click.echo(json.dumps(processes))
            return

        if not processes:
            click.echo("No active agent processes found.")
            return

        click.echo(f"{'PID':<10} {'TRACKED':<10} {'CHAT_ID':<20} {'COMMAND'}")
        click.echo("-" * 80)
        for p in processes:
            tracked = "Yes" if p.get("tracked", True) else "No"
            chat_id = p.get("chat_id") or "N/A"
            click.echo(f"{p['pid']:<10} {tracked:<10} {chat_id:<20} {p['command'][:100]}")
    cli.add_command(ps)
