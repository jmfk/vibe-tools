import click

from vibe_tools.utils import get_vibe_status_report, output_manager


def register_status(cli):
    @click.command()
    def status():
        """Display a comprehensive system status report."""
        report = get_vibe_status_report()
        if output_manager._server_mode:
            output_manager.set_final_result(0, {"report": report})
        else:
            click.echo(report)

    cli.add_command(status)
