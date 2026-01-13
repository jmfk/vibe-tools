import click

from vibe_tools.coverage import improve_coverage_loop


def register_coverage(cli):
    @click.command()
    @click.pass_context
    def coverage(ctx):
        """Run the coverage improvement loop."""
        improve_coverage_loop(
            agent=ctx.obj["agent"],
            stream=ctx.obj.get("stream", False),
        )

    cli.add_command(coverage)
