import click

from vibe_tools.utils import (
    ARCHITECTURE_CURRENT,
    ARCHITECTURE_SPEC,
    check_dependencies,
    load_project_state,
    save_project_state,
    diagnose_setup_failure,
)


def _run_setup_then_implement(ctx):
    """Run setup (with --import-code if no spec), then run implementation loop."""
    root_ctx = ctx.find_root()
    cli_group = root_ctx.command
    setup_cmd = cli_group.get_command(root_ctx, "setup")
    if not setup_cmd:
        return False
    if not ARCHITECTURE_SPEC.exists():
        click.echo("Running vibe setup --import-code to generate architecture...")
        ctx.invoke(setup_cmd, import_code=True, only_arch=False, only_scaffold=False)
        if not ARCHITECTURE_SPEC.exists():
            return False
    if not ARCHITECTURE_CURRENT.exists():
        click.echo("Running vibe setup to reconcile architecture...")
        ctx.invoke(setup_cmd, import_code=False, only_arch=False, only_scaffold=False)
    state = load_project_state()
    if state["phases"]["setup"]["status"] != "completed":
        return False
    from vibe_tools.ralph import implementation_loop
    from vibe_tools.command_output import output_manager

    agent = ctx.obj.get("agent", "cursor-agent")
    model = ctx.obj.get("model")
    stream = ctx.obj.get("stream", False)
    success = implementation_loop(agent, model=model, stream=stream)
    if success:
        click.echo("✅ Implementation cycle complete.")
        if output_manager._server_mode:
            output_manager.set_final_result(0, {"status": "complete"})
    else:
        click.echo("❌ Implementation failed or blocked. Check PRD history.")
        if output_manager._server_mode:
            output_manager.set_final_result(1, {"status": "failed"})
    return success


def register_implement(cli):
    @click.command()
    @click.pass_context
    def implement(ctx):
        """Phase 4: Implement. Iterates through product backlog items."""
        state = load_project_state()

        # Generate architecture-current.yaml if missing (run setup then implement)
        if not ARCHITECTURE_CURRENT.exists():
            click.echo("implementation/architecture-current.yaml missing; running setup to generate it...")
            from vibe_tools.agent import verify_agent_auth

            success, message = verify_agent_auth(ctx.obj.get("agent", "cursor-agent"))
            if not success:
                click.echo(click.style(message, fg="red", bold=True))
                return
            if _run_setup_then_implement(ctx) is not False:
                return
            click.echo(diagnose_setup_failure())
            return

        missing = check_dependencies("implement", state)
        # Allow implement when architecture-current.yaml exists; mark setup completed so state is consistent
        if missing and "setup" in [m.split(" ")[0] for m in missing]:
            missing = [m for m in missing if m.split(" ")[0] != "setup"]
            state["phases"]["setup"]["status"] = "completed"
            save_project_state(state)
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
        model = ctx.obj.get("model")
        stream = ctx.obj.get("stream", False)

        # Early health check for the agent
        from vibe_tools.agent import verify_agent_auth

        success, message = verify_agent_auth(agent)
        if not success:
            click.echo(click.style(message, fg="red", bold=True))
            return

        success = implementation_loop(agent, model=model, stream=stream)
        if success:
            click.echo("✅ Implementation cycle complete.")
            if output_manager._server_mode:
                output_manager.set_final_result(0, {"status": "complete"})
        else:
            click.echo("❌ Implementation failed or blocked. Check PRD history.")
            if output_manager._server_mode:
                output_manager.set_final_result(1, {"status": "failed"})

    cli.add_command(implement)
