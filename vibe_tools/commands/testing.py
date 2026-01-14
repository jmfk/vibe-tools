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
    @click.group(invoke_without_command=True, name="testing")
    @click.pass_context
    def testing(ctx):
        """Phase 7: Testing reconciliation. Ensures integration and regression tests pass."""
        if ctx.invoked_subcommand is not None:
            return

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

    @testing.command()
    @click.argument("test_id")
    @click.argument("step_id")
    @click.argument("status")
    def step(test_id, step_id, status):
        """Update the status of a test step."""
        import yaml
        from vibe_tools.utils import VIBE_PROJECT_DIR
        
        test_file = VIBE_PROJECT_DIR / "testing.yaml"
        if not test_file.exists():
            click.echo(f"❌ {test_file} not found.")
            return

        try:
            data = yaml.safe_load(test_file.read_text()) or {}
        except Exception as e:
            click.echo(f"❌ Failed to load testing.yaml: {e}")
            return

        tests = data.get("tests", [])
        updated = False
        for t in tests:
            if t.get("id") == test_id:
                for s in t.get("steps", []):
                    if s.get("id") == step_id:
                        s["status"] = status
                        updated = True
                
                # Update test status based on steps
                all_passed = all(s.get("status") == "passed" for s in t.get("steps", []))
                any_failed = any(s.get("status") == "failed" for s in t.get("steps", []))
                any_in_progress = any(s.get("status") == "in_progress" for s in t.get("steps", []))
                
                if any_failed:
                    t["status"] = "failed"
                elif all_passed:
                    t["status"] = "passed"
                elif any_in_progress:
                    t["status"] = "in_progress"
                else:
                    t["status"] = "pending"
                    
        if updated:
            test_file.write_text(yaml.dump(data, sort_keys=False))
            click.echo(f"✅ Updated {test_id}/{step_id} to {status}")
        else:
            click.echo(f"❌ Step {step_id} in test {test_id} not found.")

    cli.add_command(testing)
