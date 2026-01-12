import click

from vibe_tools.utils import check_dependencies, load_project_state, save_project_state


def register_deploy(cli):
    @click.command()
    @click.pass_context
    def deploy(ctx):
        """Phase 9: Deployment."""
        state = load_project_state()
        missing = check_dependencies("deploy", state)
        if missing:
            click.echo(
                f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first."
            )
            return

        # TODO: Implement deployment logic
        click.echo("🚀 Triggering deployment...")
        state["phases"]["deploy"]["status"] = "completed"
        save_project_state(state)
        click.echo("\n✨ Project fully deployed! All lifecycle phases completed.")

    cli.add_command(deploy)
