import atexit
import datetime
import json
import logging
import os
import pathlib
import shutil
import subprocess
from typing import Any, Dict, List

import click
import yaml
from dotenv import find_dotenv, load_dotenv

from vibe_tools.cost import finalize_cost_report, get_total_cost
from vibe_tools.setup import SERVICE_DEFINITIONS, install_deps, maybe_init_git
from vibe_tools.templates import TEMPLATES
from vibe_tools.normalize import normalize_to_data
from vibe_tools.utils import (
    ARCHITECTURE_CURRENT,
    ARCHITECTURE_SPEC,
    DEV_ENV_CURRENT,
    DEV_SPEC,
    CICD_SPEC,
    COSTS_DIR,
    INFRA_CURRENT,
    INFRA_SPEC,
    LOGS_DIR,
    TESTING_CURRENT,
    TESTING_SPEC,
    VIBE_PROJECT_DIR,
    check_dependencies,
    cleanup_stale_processes,
    enable_console_debug,
    ensure_dir,
    ensure_gitignore,
    get_agent_command,
    get_agent_processes,
    get_automerge_branch,
    get_file_hash,
    get_google_api_key,
    get_main_branch,
    get_prompt,
    is_test_mode,
    load_config,
    load_project_state,
    logger,
    reset_prd_state,
    run_agent,
    run_command,
    load_pids,
    save_pids,
    get_services,
    test_build_services,
    check_and_install_build_tools,
    save_config,
    save_project_state,
    setup_logging,
    safe_yaml_load,
    safe_yaml_dump,
)

# Load environment variables from .env file at startup
load_dotenv(find_dotenv() or ".env")

CONFIG_FILE = pathlib.Path(".vibe_config.json")
SPECS_DIR = pathlib.Path("product")


from vibe_tools.version import __version__


class OrderedGroup(click.Group):
    """Custom Click Group to order commands in the help menu."""

    def list_commands(self, ctx: click.Context) -> List[str]:
        # Define the desired order of commands
        order = [
            # Phases 1-8
            "architect",
            "pm",
            "setup",
            "deps",
            "implement",
            "build",
            "run",
            "start",
            "stop",
            "run-status",
            "infra",
            "testing",
            "cicd",
            "deploy",
            # Supporting tools
            "history",
            "status",
            "cost",
            "stats",
            "docs",
            "memory",
            "rerun",
            "implemented",
            "ps",
            "kill",
            "test-fix",
            "coverage",
            "billing-groups",
            "demo-data",
            "init",
            "sync",
            "investigate",
            "solve",
            "monitor",
        ]

        # Get the actual commands available
        commands = super().list_commands(ctx)

        # Order the commands based on the defined order, putting any unknown commands at the end
        ordered_commands = [cmd for cmd in order if cmd in commands]
        other_commands = sorted([cmd for cmd in commands if cmd not in order])

        return ordered_commands + other_commands


@click.group(invoke_without_command=True, cls=OrderedGroup)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable debug logging to console.",
)
@click.option(
    "--verbose/--no-verbose",
    default=None,
    help="Output verbose information (like prompts) to the terminal.",
)
@click.option(
    "--stream/--no-stream",
    default=None,
    help="Stream agent output in real-time to the console.",
)
@click.option(
    "--agent",
    type=click.Choice(["cursor-agent", "claude", "antigravity", "gemini"]),
    default=None,
    help="Select the agent to use.",
)
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx, debug, verbose, stream, agent):
    # Initialize logging for the invoked command
    command_name = ctx.invoked_subcommand or "info"
    setup_logging(command_name)

    # Register session cost reporting at exit
    atexit.register(finalize_cost_report)

    # Ensure files are in the right place
    from vibe_tools.utils import migrate_to_project_dir

    if not is_test_mode():
        migrate_to_project_dir()

    config = load_config()

    if stream is None:
        stream = config.get("agent", {}).get("stream")
        if stream is None:
            stream = config.get("stream", False)

    if agent is None:
        agent = config.get("agent", {}).get("agent", "cursor-agent")

    ctx.ensure_object(dict)
    ctx.obj["agent"] = agent
    ctx.obj["stream"] = stream

    if debug:
        enable_console_debug()
    else:
        # Default to WARNING level for terminal if not verbose
        if verbose is None:
            verbose = config.get("verbose", False)

        from vibe_tools.utils import set_console_level

        if verbose:
            set_console_level(logging.INFO)
        else:
            set_console_level(logging.WARNING)

    ctx.obj["verbose"] = verbose

    default_budget = config.get("default_budget", 5.0)
    ctx.obj["default_budget"] = default_budget

    if ctx.invoked_subcommand is None:
        click.echo("vibe-tools configuration:")
        click.echo(f"  Agent: {agent}")
        click.echo(f"  Stream: {'ON' if stream else 'OFF'}")
        click.echo(f"  Verbose: {'ON' if verbose else 'OFF'}")
        click.echo(f"  Default Budget: ${default_budget:.2f} USD")

        project_init = VIBE_PROJECT_DIR.exists()
        click.echo(f"  Initialized: {'Yes' if project_init else 'No'}")

        google_api_key = get_google_api_key()
        click.echo(f"  Google API Key: {'SET' if google_api_key else 'NOT SET'}")

        coverage_targets = config.get(
            "coverage_targets", {"backend": 85, "frontend": 85, "infra": 85}
        )
        click.echo("  Coverage Targets:")
        click.echo(f"    Backend:    {coverage_targets.get('backend', 85)}%")
        click.echo(f"    Frontend:   {coverage_targets.get('frontend', 85)}%")
        click.echo(f"    Infra:      {coverage_targets.get('infra', 85)}%")

        services_config = config.get("services", {})
        if services_config:
            click.echo("  Services:")
            for service_key in sorted(services_config):
                service_data = services_config[service_key]
                metadata = SERVICE_DEFINITIONS.get(service_key, {})
                display_name = metadata.get("display", service_key.capitalize())
                host = service_data.get("host", "localhost")
                port = service_data.get("port", "n/a")
                click.echo(f"    {display_name}: {host}:{port}")

        specs_dir = (
            pathlib.Path("product")
            if pathlib.Path("product").exists()
            else pathlib.Path("product")
        )
        click.echo(
            f"  Planning Directory: {specs_dir if specs_dir.exists() else 'Not found (defaults to product/)'}"
        )

        if not project_init:
            click.echo("\nRun 'vibe init' to set up templates.")
            click.echo("Run 'vibe config api' to configure LLM access.")

        click.echo("\nAvailable commands:")
        for command in cli.list_commands(ctx):
            cmd_obj = cli.get_command(ctx, command)
            if cmd_obj:
                click.echo(f"  {command:<10} {cmd_obj.get_short_help_str()}")

        click.echo("\nRun 'vibe --help' for full options.")


# Register all commands from the commands module
from vibe_tools.commands import register_all_commands

register_all_commands(cli)


@cli.group(invoke_without_command=True)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force build even if dev_environment.yaml and dev_environment-current.yaml are identical.",
)
@click.pass_context
def build(ctx, force):
    """Build the application and verify it runs."""
    if ctx.invoked_subcommand is None:
        _build_reconciliation(ctx, force)


def _build_reconciliation(ctx, force):
    """Build the application and verify it runs."""
    if not DEV_SPEC.exists():
        click.echo(f"❌ {DEV_SPEC} not found.")
        click.echo(
            "   Please run 'vibe config scaffold' first to generate development environment scaffolding."
        )
        return

    # Normalize dev_environment.md just-in-time
    click.echo(f"🔄 Normalizing {DEV_SPEC.name} in-memory...")
    dev_data = normalize_to_data(DEV_SPEC.read_text(), "dev_environment")
    if not dev_data:
        click.echo("❌ Normalization failed. Please check the content of dev_environment.md.")
        return
    
    dev_yaml = safe_yaml_dump(dev_data)
    import hashlib
    dev_hash = hashlib.sha256(dev_yaml.encode()).hexdigest()

    # Check if dev_environment.md and dev_environment-current.yaml are identical (skip if so, unless forced)
    if not force and DEV_ENV_CURRENT.exists():
        if dev_hash == get_file_hash(DEV_ENV_CURRENT):
            click.echo(
                "✅ Development environment is up-to-date. Skipping build."
            )
            click.echo("   Use --force to rebuild anyway.")
            return

    click.echo("\n--- Building Application ---")

    # Run actual build commands from Makefile or dev_environment.yaml
    click.echo("Running build commands...")

    # Try to run make build if Makefile exists
    makefile = pathlib.Path("Makefile")
    if makefile.exists():
        click.echo("  Running 'make build'...")
        result = run_command(["make", "build"], check=False)
        if result[1] != 0:
            click.echo("  ⚠️  'make build' failed. Trying individual build steps...")
            # Try backend build
            result = run_command(["make", "build-backend"], check=False)
            if result[1] == 0:
                click.echo("  ✅ Backend build succeeded")
            # Try frontend build
            result = run_command(["make", "build-frontend"], check=False)
            if result[1] == 0:
                click.echo("  ✅ Frontend build succeeded")
        else:
            click.echo("  ✅ Build completed successfully")
    else:
        # Fallback: install dependencies
        click.echo("  No Makefile found. Installing dependencies...")
        if pathlib.Path("pyproject.toml").exists():
            run_command(["pip", "install", "-e", "."], check=False)
        if pathlib.Path("frontend/package.json").exists():
            run_command(["npm", "install", "--prefix", "frontend"], check=False)
            run_command(["npm", "run", "build", "--prefix", "frontend"], check=False)

    # Test that services can start
    click.echo("\n🧪 Testing that application can start...")
    test_success = test_build_services(debug=ctx.obj.get("debug", False))

    if test_success:
        click.echo("✅ Build complete and application verified working.")

        # Save the normalized YAML to DEV_ENV_CURRENT to mark as successful
        DEV_ENV_CURRENT.write_text(dev_yaml)

        success = True
    else:
        click.echo("❌ Application failed to start after build.")
        success = False

    if success:
        click.echo("\nNext Steps:")

        # Check what services are available and provide appropriate instructions
        services = get_services()
        has_skaffold = any(
            s.get("name") == "skaffold-dev"
            or "skaffold" in s.get("start_command", "").lower()
            for s in services
        )
        has_make_dev = any(
            "make dev" in s.get("start_command", "")
            or "make dev-start" in s.get("start_command", "")
            for s in services
        )

        if has_skaffold:
            click.echo("[ ] Start development with Skaffold:")
            click.echo("     skaffold dev")
            click.echo(
                "     (This will build and deploy to your local Kubernetes cluster)"
            )
        elif has_make_dev:
            make_cmd = next(
                (
                    s.get("start_command")
                    for s in services
                    if "make dev" in s.get("start_command", "")
                ),
                "make dev-start",
            )
            click.echo("[ ] Start development services:")
            click.echo(f"     {make_cmd}")
        else:
            click.echo(
                "[ ] Start development services using the commands from your Makefile"
            )
    else:
        click.echo("❌ Development environment reconciliation failed.")


@build.command(name="debug")
@click.pass_context
def build_debug(ctx):
    """Debug the development environment scaffolding process."""
    click.echo("🔍 Debugging development environment scaffolding...")

    # Check build files
    click.echo("\n📋 Development Environment Files Status:")
    click.echo(
        f"  DEV_SPEC ({DEV_SPEC}): {'✅ exists' if DEV_SPEC.exists() else '❌ missing'}"
    )
    click.echo(
        f"  DEV_ENV_CURRENT ({DEV_ENV_CURRENT}): {'✅ exists' if DEV_ENV_CURRENT.exists() else '❌ missing'}"
    )
    click.echo(
        f"  ARCHITECTURE_SPEC ({ARCHITECTURE_SPEC}): {'✅ exists' if ARCHITECTURE_SPEC.exists() else '❌ missing'}"
    )

    # Check scaffolding-related files
    click.echo("\n🏗️  Scaffolding Files:")
    skaffold_yaml = pathlib.Path("skaffold.yaml")
    click.echo(
        f"  skaffold.yaml: {'✅ exists' if skaffold_yaml.exists() else '❌ missing'}"
    )

    makefile = pathlib.Path("Makefile")
    click.echo(f"  Makefile: {'✅ exists' if makefile.exists() else '❌ missing'}")

    # Check logging setup
    click.echo("\n📊 Logging Solution:")
    logs_dir = LOGS_DIR
    click.echo(
        f"  Logs directory ({logs_dir}): {'✅ exists' if logs_dir.exists() else '❌ missing'}"
    )

    if makefile.exists():
        try:
            makefile_content = makefile.read_text()
            has_logs_target = (
                "logs:" in makefile_content
                or "logs-backend:" in makefile_content
                or "logs-frontend:" in makefile_content
            )
            click.echo(
                f"  Makefile log targets: {'✅ found' if has_logs_target else '❌ missing'}"
            )

            # Check for specific log targets
            log_targets = []
            if "logs:" in makefile_content:
                log_targets.append("logs")
            if "logs-backend:" in makefile_content:
                log_targets.append("logs-backend")
            if "logs-frontend:" in makefile_content:
                log_targets.append("logs-frontend")
            if "logs-follow:" in makefile_content:
                log_targets.append("logs-follow")
            if "logs-clean:" in makefile_content:
                log_targets.append("logs-clean")

            if log_targets:
                click.echo(f"    Found targets: {', '.join(log_targets)}")
        except Exception as e:
            click.echo(f"  ⚠️  Error checking Makefile: {e}")
    else:
        click.echo("  ⚠️  Makefile not found, cannot check log targets")

    # Check for log aggregation services
    if DEV_ENV_CURRENT.exists():
        try:
            build_config = safe_yaml_load(DEV_ENV_CURRENT.read_text())
            if build_config:
                services = build_config.get("services", [])
                log_services = [
                    s
                    for s in services
                    if "log" in s.get("name", "").lower()
                    or "loki" in s.get("name", "").lower()
                    or "elastic" in s.get("name", "").lower()
                ]
                if log_services:
                    click.echo(
                        f"  Log aggregation services: ✅ found {len(log_services)}"
                    )
                    for svc in log_services:
                        click.echo(f"    - {svc.get('name', 'unknown')}")
                else:
                    click.echo("  Log aggregation services: ⚠️  none detected")
        except Exception as e:
            click.echo(f"  ⚠️  Error checking build config: {e}")

    # Check build tools
    click.echo("\n🔧 Build Tools:")
    check_and_install_build_tools()

    # Show services if dev_environment-current.yaml exists
    if DEV_ENV_CURRENT.exists():
        click.echo("\n📦 Detected Services:")
        try:
            services = get_services()
            if services:
                for i, service in enumerate(services, 1):
                    click.echo(f"  {i}. {service.get('name', 'unknown')}")
                    click.echo(f"     Command: {service.get('start_command', 'N/A')}")
                    if service.get("port"):
                        click.echo(f"     Port: {service.get('port')}")
                    if service.get("url"):
                        click.echo(f"     URL: {service.get('url')}")
            else:
                click.echo("  No services detected")
        except Exception as e:
            click.echo(f"  ⚠️  Error detecting services: {e}")

    # Show dev_environment.md content if it exists
    if DEV_SPEC.exists():
        click.echo(
            "\n📄 Development Environment Specification Preview (first 20 lines):"
        )
        try:
            content = DEV_SPEC.read_text()
            lines = content.splitlines()[:20]
            for line in lines:
                click.echo(f"  {line}")
            if len(content.splitlines()) > 20:
                click.echo(f"  ... ({len(content.splitlines()) - 20} more lines)")

            # Check if logging section exists
            if "logging" in content.lower() or "log" in content.lower():
                click.echo(
                    "\n  ✅ Logging section found in development environment specification"
                )
            else:
                click.echo("\n  ⚠️  No logging section found in build specification")
        except Exception as e:
            click.echo(f"  ⚠️  Error reading dev_environment.md: {e}")


@cli.command()
@click.pass_context
def stop(ctx):
    """Stop all active services."""
    from vibe_tools.utils import load_pids, save_pids, get_services, run_command
    import time

    services = get_services()
    if not services:
        click.echo("No services found to stop.")
        return

    stopped_count = 0
    pids = load_pids()

    for service in services:
        service_name = service.get("name", "unknown")
        pid_info = pids.get(service_name, {})

        # Kill background services
        background_services = pid_info.get("background_services", {})
        for service_type, bg_pid in background_services.items():
            try:
                run_command(["kill", str(bg_pid)], check=False)
                click.echo(
                    f"Stopped background service {service_name} ({service_type})"
                )
            except Exception:
                pass

        # Kill main PID
        main_pid = pid_info.get("main_pid")
        if main_pid:
            try:
                run_command(["kill", str(main_pid)], check=False)
                click.echo(f"Stopped {service_name}")
                stopped_count += 1
            except Exception:
                pass

        # Kill child PIDs
        child_pids = pid_info.get("child_pids", [])
        for child_pid in child_pids:
            try:
                run_command(["kill", str(child_pid)], check=False)
            except Exception:
                pass

    save_pids({})
    if stopped_count > 0:
        click.echo(f"Stopped {stopped_count} service(s)")
    else:
        click.echo("No active services found to stop.")


if __name__ == "__main__":
    cli()
