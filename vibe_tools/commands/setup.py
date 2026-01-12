import click

from vibe_tools.ralph import COMPLETION_PROMISE, RalphLoop
from vibe_tools.utils import (
    ARCHITECTURE,
    ARCHITECTURE_CURRENT,
    ARCHITECTURE_SPEC,
    INFRA_CURRENT,
    INFRA_SPEC,
    ensure_project_structure,
    get_agent_command,
    get_file_hash,
    get_prompt,
    load_project_state,
    run_agent,
    save_project_state,
)


def register_setup(cli):
    @click.command()
    @click.option(
        "--import-code",
        "import_code",
        is_flag=True,
        help="Import existing codebase to generate architecture-current.yaml.",
    )
    @click.pass_context
    def setup(ctx, import_code):
        """Phase 3: Architecture Setup. Reconciles architecture.yaml with architecture-current.yaml."""
        state = load_project_state()
        agent = ctx.obj.get("agent", "cursor-agent")
        stream = ctx.obj.get("stream", False)

        if import_code:
            # Ensure project directory exists before agent runs
            ensure_project_structure()

            click.echo(
                "🔍 Analyzing codebase to generate architecture and infrastructure definitions..."
            )
            try:
                prompt_template = get_prompt("discovery_prompt.txt")
            except FileNotFoundError as e:
                click.echo(f"Error: {e}")
                return

            prompt = prompt_template.format(
                architecture_current=ARCHITECTURE_CURRENT,
                infra_current=INFRA_CURRENT,
                architecture_spec=ARCHITECTURE_SPEC,
                infra_spec=INFRA_SPEC,
            )
            cmd = get_agent_command(agent, prompt)
            output, code = run_agent(cmd, stream=stream)

            if code == 0 and COMPLETION_PROMISE in output:
                click.echo("✅ Generated current state and specification files.")
                click.echo("\nNext Steps:")
                click.echo(f"1. Review {ARCHITECTURE_SPEC} and {INFRA_SPEC}")
                click.echo(
                    "2. Run 'vibe normalize' to create the desired state YAML files."
                )
                click.echo("3. Run 'vibe setup' (without --import-code) to reconcile.")
            else:
                click.echo("❌ Failed to generate discovery files.")
            return

        if not ARCHITECTURE.exists():
            if ARCHITECTURE_SPEC.exists():
                click.echo(f"❌ {ARCHITECTURE} not found, but {ARCHITECTURE_SPEC} exists.")
                click.echo("   Run 'vibe normalize' to generate the required YAML file.")
            else:
                click.echo(
                    f"❌ {ARCHITECTURE} not found. Please create it manually or via 'vibe architect' + 'vibe normalize'."
                )
            return

        # Run the reconciliation loop
        loop = RalphLoop(
            name="Architecture Setup",
            desired_file=ARCHITECTURE,
            current_file=ARCHITECTURE_CURRENT,
            agent=agent,
            stream=stream,
        )

        loop.instructions = [
            "Initialize or update the testing infrastructure for both frontend and backend.",
            "Ensure the Makefile has working 'test-backend' and 'test-frontend' targets that match the architecture.",
            "Create dummy test files (e.g., backend/tests/test_initial.py, frontend/src/initial.test.ts) to verify the harness. Use explicit imports in frontend tests (import from 'vitest').",
            "Ensure test dependencies and scripts are present in pyproject.toml and package.json. For React 18, use @testing-library/react ^14 or ^15.",
        ]

        success = loop.run()
        if success:
            state["phases"]["setup"]["status"] = "completed"
            state["phases"]["setup"]["hash"] = get_file_hash(ARCHITECTURE)
            save_project_state(state)
            click.echo("\n✅ Architecture setup complete. project-state.json updated.")

            # Generate the project plan based on PRDs
            from vibe_tools.ralph import generate_prd_plan

            generate_prd_plan()

            # Run scaffold to set up development environment infrastructure and logging
            click.echo("\n--- Running Development Environment Scaffolding Setup ---")
            try:
                from vibe_tools.setup import scaffold
                # Create a minimal context object for scaffold
                scaffold_ctx = click.Context(click.Command("scaffold"))
                scaffold_ctx.obj = ctx.obj
                scaffold(scaffold_ctx)
            except Exception as e:
                click.echo(f"⚠️  Scaffold setup encountered an error: {e}")
                click.echo("   You can run 'vibe config scaffold' manually to set up development environment infrastructure.")

            click.echo("\nNext Steps:")
            click.echo("1. Run 'vibe deps' to install any new testing dependencies.")
            click.echo("2. Start Building (vibe implement)")
        else:
            click.echo("❌ Architecture setup failed.")

    cli.add_command(setup)
