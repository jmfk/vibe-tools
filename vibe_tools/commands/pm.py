import click

from vibe_tools.pm import InteractivePM


def register_pm(cli):
    @click.command()
    @click.argument("query", required=False)
    @click.pass_context
    def pm(ctx, query):
        """Phase 1: Interactive PRD and specification manager."""
        pm_tool = InteractivePM(
            agent_type=ctx.obj.get("agent", "cursor-agent"),
            stream=ctx.obj.get("stream", True),
        )
        pm_tool.run(query)
