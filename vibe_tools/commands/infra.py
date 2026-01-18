import click

from vibe_tools.architect import generate_infrastructure_spec
from vibe_tools.normalize import normalize_to_data
from vibe_tools.ralph import RalphLoop
from vibe_tools.utils import (
    INFRA_CURRENT,
    INFRA_SPEC,
    check_dependencies,
    load_project_state,
    safe_yaml_dump,
)


def register_infra(cli):
    @click.command()
    @click.option(
        "--spec",
        "only_spec",
        is_flag=True,
        help="Only generate or update the infrastructure specification.",
    )
    @click.pass_context
    def infra(ctx, only_spec):
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

        agent = ctx.obj.get("agent", "cursor-agent")
        stream = ctx.obj.get("stream", False)

        # Early health check for the agent
        from vibe_tools.agent import verify_agent_auth

        success, message = verify_agent_auth(agent)
        if not success:
            click.echo(click.style(message, fg="red", bold=True))
            return

        # Ensure infrastructure spec exists
        if not INFRA_SPEC.exists() or only_spec:
            # generate from PRDs if it doesn't exist
            click.echo(f"📝 Generating/Updating {INFRA_SPEC} from PRDs...")
            generate_infrastructure_spec(
                agent=agent,
            )
            if not INFRA_SPEC.exists():
                click.echo(
                    "❌ Failed to generate infrastructure spec. Please create SRD-infrastructure.md manually."
                )
                return
            if only_spec:
                return

        # Normalize SRD-infrastructure.md just-in-time
        click.echo(f"🔄 Normalizing {INFRA_SPEC.name} in-memory...")
        infra_data = normalize_to_data(INFRA_SPEC.read_text(), "infrastructure")
        if not infra_data:
            click.echo(
                "❌ Normalization failed. Please check the content of SRD-infrastructure.md."
            )
            return

        infra_yaml = safe_yaml_dump(infra_data)

        # Run infrastructure reconciliation
        loop = RalphLoop(
            name="Infrastructure",
            desired_content=infra_yaml,
            desired_file_name=INFRA_SPEC.name,
            current_file=INFRA_CURRENT,
            agent=agent,
            stream=stream,
        )
        loop.run()

    cli.add_command(infra)
