import click

from vibe_tools.architect import generate_infrastructure_spec
from vibe_tools.normalize import normalize_prd
from vibe_tools.ralph import RalphLoop
from vibe_tools.utils import (
    INFRA,
    INFRA_CURRENT,
    INFRA_SPEC,
    check_dependencies,
    load_project_state,
)


def register_infra(cli):
    @click.command()
    @click.pass_context
    def infra(ctx):
        """Phase 6: Infrastructure reconciliation for production and live-staging environments.

        Sets up infrastructure for production and live-staging systems (Kubernetes, cloud platforms, etc.).
        This step is optional depending on the distribution needs of the project - not all projects
        require a production environment.

        Note: For development environment management, use 'vibe build' instead.
        """
        state = load_project_state()
        missing = check_dependencies("infra", state)
        if missing:
            click.echo(
                f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first."
            )
            return

        # Handle missing infrastructure files
        if not INFRA.exists():
            if INFRA_SPEC.exists():
                # infrastructure.md exists but not normalized - auto-normalize it
                click.echo(f"📝 {INFRA_SPEC} found but not normalized. Normalizing...")
                normalize_prd(
                    input_file=str(INFRA_SPEC),
                    auto_overwrite=True,
                )
                if not INFRA.exists():
                    click.echo(
                        "❌ Normalization failed. Please review and fix infrastructure.md, then run 'vibe normalize' manually."
                    )
                    return
                click.echo("✅ Infrastructure normalized successfully.")
            else:
                # Neither exists - generate from PRDs
                click.echo(f"📝 Generating {INFRA_SPEC} from PRDs...")
                generate_infrastructure_spec(
                    agent=ctx.obj.get("agent", "cursor-agent"),
                )
                if INFRA_SPEC.exists():
                    normalize_prd(
                        input_file=str(INFRA_SPEC),
                        auto_overwrite=True,
                    )
                else:
                    click.echo(
                        "❌ Failed to generate infrastructure spec. Please create infrastructure.md manually."
                    )
                    return

        # Run infrastructure reconciliation
        loop = RalphLoop(
            name="Infrastructure",
            desired_file=INFRA,
            current_file=INFRA_CURRENT,
            agent=ctx.obj.get("agent", "cursor-agent"),
            stream=ctx.obj.get("stream", False),
        )
        loop.run()

    cli.add_command(infra)
