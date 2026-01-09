import click

from vibe_tools.utils import check_dependencies, collect_prd_files, load_project_state


def register_implement(cli):
    @click.command()
    @click.pass_context
    def implement(ctx):
        """Phase 5: Implement. Iterates through implementation plans defined in state.json."""
        state = load_project_state()
        missing = check_dependencies("implement", state)
        if missing:
            click.echo(
                f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first."
            )
            return

        if not collect_prd_files():
            click.echo("❌ No machine-readable PRD YAMLs found in product/prds/backlog/.")
            click.echo(
                "   Run 'vibe pm' to refine specs and 'vibe normalize' to generate them."
            )
            return

        from vibe_tools.ralph import implementation_loop

        agent = ctx.obj.get("agent", "cursor-agent")
        stream = ctx.obj.get("stream", False)

        success = implementation_loop(agent, stream=stream)
        if success:
            state["phases"]["implement"]["status"] = "completed"
            from vibe_tools.utils import save_project_state
            save_project_state(state)
            click.echo("✅ Implementation complete.")
            click.echo("\nNext Steps:")
            click.echo("[ ] Run Tests & Reconciliation (vibe testing)")
        else:
            click.echo("❌ Implementation failed.")
