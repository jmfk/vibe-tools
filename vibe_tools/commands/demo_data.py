import pathlib

import click

from vibe_tools.pm import InteractivePM
from vibe_tools.staging import (
    check_service_health,
    detect_environment,
    get_required_services,
    staging_cli,
)
from vibe_tools.utils import (
    SPECS_DIR,
    ensure_dir,
    get_agent_command,
    logger,
    run_agent,
)


def register_demo_data(cli):
    @click.group()
    def demo_data_cli():
        """Manage demo data for staging environment."""
        pass

    @demo_data_cli.command()
    @click.pass_context
    def design(ctx):
        """Design demo data PRD in specs/demodata.md using PM system."""
        agent = ctx.obj.get("agent", "cursor-agent")
        stream = ctx.obj.get("stream", False)
        verbose = ctx.obj.get("verbose", False)

        pm = InteractivePM(agent=agent, stream=stream, verbose=verbose)

        # Focus on demodata.md
        demodata_path = SPECS_DIR / "demodata.md"
        if not demodata_path.exists():
            ensure_dir(SPECS_DIR)
            template = """# Demo Data

## Summary
Define the demo data needed for the staging environment.

## Requirements

### Data Requirements
- What entities need demo data?
- What relationships should be established?
- What realistic scenarios should be represented?

### Data Setup
- How should the data be loaded?
- What scripts or tools are needed?
- What cleanup is required for a clean demo?

## Implementation
"""
            demodata_path.write_text(template)
            click.echo(f"✅ Created {demodata_path}")

        pm.focused_prd = "demodata.md"
        click.echo(f"📝 Opening PM session focused on demodata.md")
        click.echo(
            "Use /mode agent to enable file editing, then describe your demo data requirements."
        )
        pm.run()

    @demo_data_cli.command()
    @click.option(
        "--clean", is_flag=True, help="Clean existing data before setting up demo data"
    )
    @click.pass_context
    def setup(ctx, clean):
        """Setup demo data according to specs/demodata.md."""
        demodata_path = SPECS_DIR / "demodata.md"
        if not demodata_path.exists():
            click.echo("❌ specs/demodata.md not found. Run 'vibe demo-data design' first.")
            return

        # Check staging is running
        env_type = detect_environment()
        services = get_required_services()
        all_healthy = True
        for service_key, service_config in services.items():
            service_name = service_key.replace("s3-", "minio-").replace("-", "_")
            is_healthy, _ = check_service_health(service_name, service_config, env_type)
            if not is_healthy:
                all_healthy = False
                break

        if not all_healthy:
            click.echo("⚠️  Some staging services are not healthy. Starting staging...")
            try:
                ctx_staging = click.Context(staging_cli)
                ctx_staging.invoke(
                    staging_cli.get_command(ctx_staging, "up"), isolated=False
                )
            except Exception as e:
                click.echo(f"  ⚠️  Staging setup warning: {e}")

        # Read demo data spec
        spec_content = demodata_path.read_text()

        agent = ctx.obj.get("agent", "cursor-agent")
        stream = ctx.obj.get("stream", False)

        # Build prompt for data setup
        prompt = f"""You are setting up demo data for a staging environment.

The demo data specification is in specs/demodata.md:

{spec_content}

TASK:
{"1. Clean/reset all existing data in the database and services (if --clean flag is set)" if clean else "1. Preserve existing data"}
2. Create and load demo data according to the specification
3. Verify the data was loaded correctly

You have access to the staging environment services. Use appropriate tools (SQL scripts, API calls, etc.) to set up the data.

{"IMPORTANT: Clean all existing data first before loading new demo data." if clean else ""}

Provide step-by-step instructions or execute the data setup directly.
"""

        cmd = get_agent_command(agent, prompt)
        output, code = run_agent(cmd, stream=stream)

        if code == 0:
            click.echo("✅ Demo data setup complete.")
        else:
            click.echo("❌ Demo data setup failed.")
            logger.error(f"Agent output: {output}")

    cli.add_command(demo_data_cli, name="demo-data")