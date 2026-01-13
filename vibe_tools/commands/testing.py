import click

from vibe_tools.ralph import RalphLoop
from vibe_tools.normalize import normalize_to_data
from vibe_tools.utils import (
    TESTING_CURRENT,
    TESTING_SPEC,
    check_dependencies,
    load_project_state,
    save_project_state,
    safe_yaml_dump,
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

        if not TESTING_SPEC.exists():
            click.echo(
                f"❌ {TESTING_SPEC} not found. Please create it manually or via 'vibe architect'."
            )
            return

        agent = ctx.obj.get("agent", "cursor-agent")
        stream = ctx.obj.get("stream", False)

        # Normalize testing.md just-in-time
        click.echo(f"🔄 Normalizing {TESTING_SPEC.name} in-memory...")
        testing_data = normalize_to_data(TESTING_SPEC.read_text(), "testing")
        if not testing_data:
            click.echo("❌ Normalization failed. Please check the content of testing.md.")
            return
        
        testing_yaml = safe_yaml_dump(testing_data)

        loop = RalphLoop(
            name="Testing",
            desired_content=testing_yaml,
            desired_file_name=TESTING_SPEC.name,
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
