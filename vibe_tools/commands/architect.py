import click

from vibe_tools.architect import InteractiveArchitect


def register_architect(cli):
    @click.command()
    @click.argument("query", required=False)
    @click.pass_context
    def architect(ctx, query):
        """Interactive architecture and infrastructure spec manager."""
        architect_tool = InteractiveArchitect(
            agent_type=ctx.obj.get("agent", "cursor-agent"),
            stream=ctx.obj.get("stream", True),
        )
        architect_tool.run_loop(query)

    cli.add_command(architect)
