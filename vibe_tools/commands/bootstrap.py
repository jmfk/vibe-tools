import click
from vibe_tools.agent import verify_agent_auth
from vibe_tools.utils import commit_project_infrastructure

def register_bootstrap(cli):
    @click.command()
    @click.pass_context
    def bootstrap(ctx):
        """Phase 0-2: Prepare product for implementation.
        
        Orchestrates initialization, architecture setup, scaffolding,
        and dependency installation without starting services.
        """
        agent = ctx.obj.get("agent", "cursor-agent")
        
        # Early health check for the agent
        success, message = verify_agent_auth(agent)
        if not success:
            click.echo(click.style(message, fg="red", bold=True))
            return

        click.echo(click.style("\n🚀 Starting product bootstrap...", fg="cyan", bold=True))
        
        # Get the main CLI group to invoke other commands
        root_ctx = ctx.find_root()
        cli_group = root_ctx.command
        
        # 1. Initialization (vibe init)
        click.echo("\n--- Step 1: Project Initialization ---")
        init_cmd = cli_group.get_command(root_ctx, "init")
        if init_cmd:
            ctx.invoke(init_cmd)
        else:
            click.echo("⚠️  Could not find 'init' command.")
        
        # 2. Setup Architecture (vibe setup)
        click.echo("\n--- Step 2: Architecture Reconciliation ---")
        setup_cmd = cli_group.get_command(root_ctx, "setup")
        if setup_cmd:
            ctx.invoke(setup_cmd)
        else:
            click.echo("⚠️  Could not find 'setup' command.")
        
        # 3. Install Dependencies (vibe deps)
        click.echo("\n--- Step 3: Dependency Installation ---")
        deps_cmd = cli_group.get_command(root_ctx, "deps")
        if deps_cmd:
            ctx.invoke(deps_cmd)
        else:
            click.echo("⚠️  Could not find 'deps' command.")
            
        # 4. Sync Makefile
        click.echo("\n--- Step 4: Synchronizing Makefile ---")
        build_group = cli_group.get_command(root_ctx, "build")
        if build_group:
            # We want to run the base 'build' command with --makefile
            # Since build is a group with invoke_without_command=True,
            # invoking it directly should work.
            ctx.invoke(build_group, only_makefile=True)
        else:
            click.echo("⚠️  Could not find 'build' command.")

        # 5. Commit Infrastructure
        commit_project_infrastructure("vibe: bootstrap complete")

        click.echo(click.style("\n✅ Bootstrap complete!", fg="green", bold=True))
        click.echo("Foundation ready. Run 'vibe implement' to start building features.")

    cli.add_command(bootstrap)
