import click

from vibe_tools.utils import (
    check_dependencies,
    load_project_state,
    diagnose_setup_failure,
)


def register_implement(cli):
    @click.command()
    @click.pass_context
    def implement(ctx):
        """Phase 4: Implement. Iterates through product backlog items."""
        state = load_project_state()

        missing = check_dependencies("implement", state)
        if missing:
            if "setup" in [m.split(" ")[0] for m in missing]:
                click.echo(diagnose_setup_failure())
            else:
                click.echo(
                    f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first."
                )
            return

        from vibe_tools.ralph import implementation_loop
        from vibe_tools.command_output import output_manager

        agent = ctx.obj.get("agent", "cursor-agent")
        stream = ctx.obj.get("stream", False)

        # Early health check for the agent
        from vibe_tools.agent import verify_agent_auth

        success, message = verify_agent_auth(agent)
        if not success:
            click.echo(click.style(message, fg="red", bold=True))
            return

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
