import click
import pathlib
from vibe_tools.utils import (
    load_project_state,
    save_project_state,
    get_agent_command,
    run_agent,
    load_config,
    get_prompt,
    test_build_services,
)
from vibe_tools.ralph import COMPLETION_PROMISE

def register_start(cli):
    @click.command()
    @click.pass_context
    def start(ctx):
        """Phase 0-5: Complete product bootstrap.
        
        Orchestrates initialization, architecture setup, scaffolding,
        dependency installation, and build verification in a single loop.
        """
        agent = ctx.obj.get("agent", "cursor-agent")
        # Early health check for the agent
        from vibe_tools.agent import verify_agent_auth
        success, message = verify_agent_auth(agent)
        if not success:
            click.echo(click.style(message, fg="red", bold=True))
            return

        click.echo(click.style("\n🚀 Starting product bootstrap loop...", fg="cyan", bold=True))
        
        stream = ctx.obj.get("stream", False)
        
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
        
        # 3. Scaffolding (vibe config scaffold)
        # Note: Setup command already calls scaffold, but we ensure it's done
        
        # 4. Install Dependencies (vibe deps)
        click.echo("\n--- Step 3: Dependency Installation ---")
        deps_cmd = cli_group.get_command(root_ctx, "deps")
        if deps_cmd:
            ctx.invoke(deps_cmd)
        else:
            click.echo("⚠️  Could not find 'deps' command.")
        
        # 5. Build & Verify (vibe build)
        click.echo("\n--- Step 4: Build & Verification ---")
        # Since 'build' is a group in cli.py, we might need to call its logic
        from vibe_tools.cli import _build_reconciliation
        _build_reconciliation(ctx, force=True)
        
        # 6. Verification & AI-Driven Fix Loop
        click.echo("\n--- Step 5: Final Verification & Fix Loop ---")
        success, logs = test_build_services(debug=ctx.obj.get("debug", False), return_report=True)
        
        if success:
            click.echo(click.style("\n✅ Product is up and running!", fg="green", bold=True))
        else:
            click.echo(click.style("\n⚠️  Verification failed. Starting AI fix loop...", fg="yellow"))
            
            try:
                fix_prompt_template = get_prompt("startup_fix_prompt.txt")
            except FileNotFoundError:
                # Fallback if prompt doesn't exist yet
                fix_prompt_template = "The product failed to start. Please analyze the logs and environment to fix the issue. Current state: {state}. Error logs: {logs}. Ask the user for feedback if needed."

            # Attempt AI fix
            for i in range(1, 4):  # 3 attempts
                click.echo(f"🛠️ Fix attempt {i}/3...")
                
                # Use actual failure logs
                state = load_project_state()
                
                prompt = fix_prompt_template.format(
                    state=state,
                    logs=logs
                )
                
                cmd = get_agent_command(agent, prompt)
                output, code = run_agent(cmd, stream=stream)
                
                if code == 0 and COMPLETION_PROMISE in output:
                    click.echo("🔄 Re-verifying after fix...")
                    success, logs = test_build_services(debug=ctx.obj.get("debug", False), return_report=True)
                    if success:
                        click.echo(click.style("\n✅ Product is now up and running!", fg="green", bold=True))
                        return
                
            click.echo(click.style("\n❌ Failed to bootstrap the product automatically.", fg="red", bold=True))
            click.echo("Please check the logs and try fixing issues manually.")

    cli.add_command(start)
