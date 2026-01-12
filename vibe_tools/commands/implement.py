import click

from vibe_tools.utils import (
    check_dependencies,
    collect_prd_files,
    load_project_state,
    get_prd_inconsistencies,
    fix_prd_inconsistencies,
)


def register_implement(cli):
    @click.command()
    @click.pass_context
    def implement(ctx):
        """Phase 5: Implement. Iterates through implementation plans defined in state.json."""
        state = load_project_state()

        # Check for PRD location inconsistencies
        inconsistencies = get_prd_inconsistencies()
        if inconsistencies:
            click.echo("⚠️  Found PRD location inconsistencies:")
            for inc in inconsistencies:
                click.echo(f"  - {inc['name']}: MD at {inc['md_path']}, YAML at {inc['yaml_path']}")
            
            if click.confirm("Fix inconsistencies to synchronize MD and YAML locations?", default=True):
                fix_prd_inconsistencies(inconsistencies, prefer_yaml=True)
                click.echo("✅ Inconsistencies fixed.")
                # Reload state after fixing
                state = load_project_state()
            else:
                click.echo("❌ Aborted. Please fix inconsistencies manually.")
                return

        missing = check_dependencies("implement", state)
        if missing:
            click.echo(
                f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first."
            )
            return

        if not collect_prd_files():
            click.echo("❌ No machine-readable PRD YAMLs found in implementation/prds/backlog/.")
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

    cli.add_command(implement)
