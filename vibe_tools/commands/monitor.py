import click

from vibe_tools.monitor import run_monitor


def register_monitor(cli):
    @click.command()
    @click.option(
        "--interval",
        type=int,
        default=60,
        help="Monitoring interval in seconds (default: 60).",
    )
    @click.pass_context
    def monitor(ctx, interval):
        """Monitor the progress of automated generation."""
        run_monitor(
            agent=ctx.obj["agent"],
            interval=interval,
            stream=ctx.obj.get("stream", False),
        )

    cli.add_command(monitor)
