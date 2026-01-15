import click

from vibe_tools.utils import (
    check_dependencies,
    load_project_state,
)


def register_implement(cli):
    @click.command()
    @click.pass_context
    def implement(ctx):
        """Phase 5: Implement. Iterates through product backlog PRDs."""
        state = load_project_state()

        missing = check_dependencies("implement", state)
        if missing:
            click.echo(
                f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first."
            )
            return

        from vibe_tools.ralph import implementation_loop
        from vibe_tools.command_output import output_manager

        agent = ctx.obj.get("agent", "cursor-agent")
        stream = ctx.obj.get("stream", False)

        success = implementation_loop(agent, stream=stream)
        if success:
            click.echo("✅ Implementation cycle complete.")
            if output_manager._server_mode:
                output_manager.set_final_result(0, {"status": "complete"})
        else:
            click.echo("❌ Implementation failed or blocked. Check PRD history.")
            if output_manager._server_mode:
                output_manager.set_final_result(1, {"status": "failed"})

    cli.add_command(implement)
