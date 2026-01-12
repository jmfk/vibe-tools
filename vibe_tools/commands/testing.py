import click

from vibe_tools.ralph import RalphLoop
from vibe_tools.utils import (
    TESTING_CONFIG,
    TESTING_CURRENT,
    TESTING_SPEC,
    check_dependencies,
    load_project_state,
    save_project_state,
)


def register_testing(cli):
    @click.command()
    @click.pass_context
    def testing(ctx):
        """Phase 7: Testing reconciliation. Ensures integration and regression tests pass."""
        state = load_project_state()
        missing = check_dependencies("testing", state)
        if missing:
            click.echo(
                f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first."
            )
            return

        if not TESTING_CONFIG.exists():
            if TESTING_SPEC.exists():
                click.echo(f"❌ {TESTING_CONFIG} not found, but {TESTING_SPEC} exists.")
                click.echo("   Run 'vibe normalize' to generate the required YAML file.")
            else:
                click.echo(
                    f"❌ {TESTING_CONFIG} not found. Please create it manually or via 'vibe architect' + 'vibe normalize'."
                )
            return

        agent = ctx.obj.get("agent", "cursor-agent")
        stream = ctx.obj.get("stream", False)

        loop = RalphLoop(
            name="Testing",
            desired_file=TESTING_CONFIG,
            current_file=TESTING_CURRENT,
            agent=agent,
            stream=stream,
        )

        loop.instructions = [
            "Ensure all integration and regression tests are passing.",
            "Update test configurations if the architecture or environment has changed.",
            "Run 'make test-integration' and 'make test-regression' to verify.",
        ]

        if loop.run():
            state["phases"]["testing"]["status"] = "completed"
            save_project_state(state)
            click.echo("✅ Testing reconciliation complete.")
            click.echo("\nNext Steps:")
            click.echo("[ ] Setup CI/CD (vibe cicd)")
        else:
            click.echo("❌ Testing reconciliation failed.")

    cli.add_command(testing)
