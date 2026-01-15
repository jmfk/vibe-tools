import click

from vibe_tools.ralph import COMPLETION_PROMISE, RalphLoop
from vibe_tools.normalize import normalize_to_data
from vibe_tools.utils import (
    ARCHITECTURE_CURRENT,
    ARCHITECTURE_SPEC,
    INFRA_CURRENT,
    INFRA_SPEC,
    ensure_project_structure,
    get_agent_command,
    get_prompt,
    load_project_state,
    run_agent,
    save_project_state,
    safe_yaml_dump,
)


def register_setup(cli):
    @click.command()
    @click.option(
        "--import-code",
        "import_code",
        is_flag=True,
        help="Import existing codebase to generate architecture-current.yaml.",
    )
    @click.option(
        "--arch",
        "only_arch",
        is_flag=True,
        help="Only run the architecture reconciliation loop.",
    )
    @click.option(
        "--scaffold",
        "only_scaffold",
        is_flag=True,
        help="Only run the development environment scaffolding.",
    )
    @click.pass_context
    def setup(ctx, import_code, only_arch, only_scaffold):
        """Phase 3: Architecture Setup. Reconciles architecture.md with architecture-current.yaml."""
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
                click.echo("2. Run 'vibe setup' (without --import-code) to reconcile.")
            else:
                click.echo("❌ Failed to generate discovery files.")
            return

        run_all = not (only_arch or only_scaffold)

        if run_all or only_arch:
            if not ARCHITECTURE_SPEC.exists():
                click.echo(
                    f"❌ {ARCHITECTURE_SPEC} not found. Please create it manually or via 'vibe architect'."
                )
                if only_arch:
                    return
            else:
                # Normalize architecture.md just-in-time
                click.echo(f"🔄 Normalizing {ARCHITECTURE_SPEC.name} in-memory...")
                arch_data = normalize_to_data(
                    ARCHITECTURE_SPEC.read_text(), "architecture"
                )
                if not arch_data:
                    click.echo(
                        "❌ Normalization failed. Please check the content of architecture.md."
                    )
                    if only_arch:
                        return
                else:
                    arch_yaml = safe_yaml_dump(arch_data)

                    # Run the reconciliation loop
                    loop = RalphLoop(
                        name="Architecture Setup",
                        desired_content=arch_yaml,
                        desired_file_name=ARCHITECTURE_SPEC.name,
                        current_file=ARCHITECTURE_CURRENT,
                        agent=agent,
                        stream=stream,
                    )

                    loop.instructions = [
                        "Initialize or update the testing infrastructure for both frontend and backend.",
                        "Ensure the Makefile has working 'test-backend' and 'test-frontend' targets that match the architecture.",
                        "Create dummy test files (e.g., tests/test_initial.py, frontend/src/initial.test.ts) to verify the harness. Use explicit imports in frontend tests (import from 'vitest').",
                        "Ensure test dependencies and scripts are present in pyproject.toml and package.json. For React 18, use @testing-library/react ^14 or ^15.",
                    ]

                    success = loop.run()
                    if success:
                        import hashlib

                        arch_hash = hashlib.sha256(arch_yaml.encode()).hexdigest()
                        state["phases"]["setup"]["status"] = "completed"
                        state["phases"]["setup"]["hash"] = arch_hash
                        save_project_state(state)
                        click.echo(
                            "\n✅ Architecture setup complete. project-state.json updated."
                        )

                        # Generate the project plan based on PRDs
                        from vibe_tools.ralph import generate_prd_plan

                        generate_prd_plan()
                    else:
                        click.echo("❌ Architecture setup failed.")
                        if only_arch:
                            return

        if run_all or only_scaffold:
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
                click.echo(
                    "   You can run 'vibe config scaffold' manually to set up development environment infrastructure."
                )

        if run_all:
            click.echo("\nNext Steps:")
            click.echo("1. Run 'vibe deps' to install any new testing dependencies.")
            click.echo("2. Start Building (vibe implement)")

    cli.add_command(setup)
