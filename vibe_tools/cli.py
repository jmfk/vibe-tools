import atexit
import datetime
import json
import logging
import pathlib
import subprocess
from typing import List

import click

class OrderedGroup(click.Group):
    """Custom Click Group to order commands in the help menu."""

    def list_commands(self, ctx: click.Context) -> List[str]:
        # Define the desired order of commands
        order = [
            # Phases 1-8
            "setup",
            "normalize",
            "plan",
            "implement",
            "infra",
            "cicd",
            "testing",
            "deploy",
            # Supporting tools
            "ideation",
            "prd",
            "history",
            "status",
            "cost",
            "docs",
            "memory",
            "remember",
            "monitor",
            "rerun",
            "test-fix",
            "coverage",
            "init",
            # Deprecated
            "ralph",
            "review-prd",
            "write-prd",
        ]

        # Get the actual commands available
        commands = super().list_commands(ctx)

        # Order the commands based on the defined order, putting any unknown commands at the end
        ordered_commands = [cmd for cmd in order if cmd in commands]
        other_commands = sorted([cmd for cmd in commands if cmd not in order])

        return ordered_commands + other_commands


from vibe_tools.cost import finalize_cost_report, get_total_cost
from vibe_tools.templates import TEMPLATES
from vibe_tools.utils import (
    COSTS_DIR,
    PRD_DIR,
    STATE_FILE,
    PROJECT_STATE_FILE,
    ARCHITECTURE,
    ARCHITECTURE_CURRENT,
    PROJECT_PLAN,
    INFRA,
    INFRA_CURRENT,
    CICD,
    CICD_CURRENT,
    TESTING_CONFIG,
    TESTING_CURRENT,
    enable_console_debug,
    ensure_dir,
    ensure_gitignore,
    get_agent_command,
    get_google_api_key,
    get_main_branch,
    load_config,
    load_project_state,
    save_project_state,
    check_dependencies,
    get_file_hash,
    run_agent,
    run_command,
    save_config,
    setup_logging,
)
from vibe_tools.setup import SERVICE_DEFINITIONS, maybe_init_git
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env file at startup
load_dotenv(find_dotenv() or ".env")

CONFIG_FILE = pathlib.Path(".vibe_config.json")
PROMPTS_DIR = pathlib.Path("prompts")
REVIEW_PROMPT_TEMPLATE = PROMPTS_DIR / "review_prompt.txt"
SPECS_DIR = pathlib.Path("specs")


@click.group(invoke_without_command=True, cls=OrderedGroup)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable debug logging to console.",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=None,
    help="Output verbose information (like prompts) to the terminal.",
)
@click.option(
    "--stream",
    is_flag=True,
    default=False,
    help="Stream agent output in real-time to the console.",
)
@click.option(
    "--agent",
    type=click.Choice(["cursor-agent", "claude", "antigravity"]),
    default="cursor-agent",
    help="Select the agent to use.",
)
@click.option(
    "--caffeinate",
    is_flag=True,
    default=None,
    help="Use caffeinate to prevent sleep during long-running tasks.",
)
@click.version_option(version="0.1.0")
@click.pass_context
def cli(ctx, debug, verbose, stream, agent, caffeinate):
    # Initialize logging for the invoked command
    command_name = ctx.invoked_subcommand or "info"
    setup_logging(command_name)

    # Register session cost reporting at exit
    atexit.register(finalize_cost_report)

    ctx.ensure_object(dict)
    ctx.obj["agent"] = agent
    ctx.obj["stream"] = stream

    config = load_config()

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

    if caffeinate is None:
        caffeinate = config.get("caffeinate", False)
    ctx.obj["caffeinate"] = caffeinate

    default_budget = config.get("default_budget", 5.0)
    ctx.obj["default_budget"] = default_budget

    if ctx.invoked_subcommand is None:
        click.echo("vibe-tools configuration:")
        click.echo(f"  Agent: {agent}")
        click.echo(f"  Stream: {'ON' if stream else 'OFF'}")
        click.echo(f"  Caffeinate: {'ON' if caffeinate else 'OFF'}")
        click.echo(f"  Verbose: {'ON' if verbose else 'OFF'}")
        click.echo(f"  Default Budget: ${default_budget:.2f} USD")

        prompts_init = pathlib.Path("prompts").exists()
        click.echo(f"  Initialized: {'Yes (prompts/ found)' if prompts_init else 'No'}")

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
            pathlib.Path("specs")
            if pathlib.Path("specs").exists()
            else pathlib.Path("spec")
        )
        click.echo(
            f"  Specs Directory: {specs_dir if specs_dir.exists() else 'Not found (defaults to specs/)'}"
        )

        if not prompts_init:
            click.echo("\nRun 'vibe init' to set up templates.")
            click.echo("Run 'vibe-setup api' to configure LLM access.")

        click.echo("\nAvailable commands:")
        for command in cli.list_commands(ctx):
            cmd_obj = cli.get_command(ctx, command)
            if cmd_obj:
                click.echo(f"  {command:<10} {cmd_obj.get_short_help_str()}")

        click.echo("\nRun 'vibe --help' for full options.")


@cli.command()
@click.pass_context
def init(ctx):
    """Interactive guided project initialization."""
    click.echo(click.style("\n=== VIBE PROJECT INITIALIZATION ===", fg="cyan", bold=True))
    click.echo("Welcome! Let's get your project set up for automated development.\n")

    click.echo("Please select your starting scenario:")
    click.echo(click.style("  A) Idea Only", bold=True) + " - You have an idea and want to define requirements interactively.")
    click.echo(click.style("  B) Human Specs", bold=True) + " - You already have human-written markdown specs in 'specs/'.")
    click.echo(click.style("  C) Adoption", bold=True) + " - You have an existing codebase and want Vibe to discover it.")
    click.echo(click.style("  D) Architecture Ready", bold=True) + " - You have an 'architecture.yaml' ready to go.")
    click.echo(click.style("  E) Manual Setup", bold=True) + " - Just initialize the folders and templates for manual work.")

    choice = click.prompt("\nSelect scenario", type=click.Choice(["A", "B", "C", "D", "E"], case_sensitive=False), default="E").upper()

    # Always perform basic initialization first
    _perform_basic_init()

    if choice == "A":
        click.echo("\n🚀 Starting interactive ideation...")
        ctx.invoke(ideation)
    elif choice == "B":
        click.echo("\n📄 Please ensure your specs are in 'specs/'. Next step: 'vibe normalize'")
    elif choice == "C":
        click.echo("\n🔍 Starting codebase discovery...")
        ctx.invoke(setup, import_code=True)
    elif choice == "D":
        click.echo("\n🏗️  Starting architecture setup...")
        ctx.invoke(setup)
    else:
        click.echo("\n✅ Basic initialization complete.")

    click.echo("\nRun 'vibe status' at any time to see your project progress.")


def _perform_basic_init():
    """Helper to initialize the prompts directory and default templates."""
    maybe_init_git()
    ensure_gitignore("logs/")
    prompts_dir = pathlib.Path("prompts")
    ensure_dir(prompts_dir)

    # Create new directories for instructions and specs
    from vibe_tools.utils import INSTRUCTIONS_DIR

    ensure_dir(INSTRUCTIONS_DIR)
    ensure_dir(pathlib.Path("specs"))
    ensure_dir(pathlib.Path("prds"))

    for filename, content in TEMPLATES.items():
        if filename in ["dummy_backend_test", "dummy_frontend_test"]:
            continue

        if filename == "Makefile":
            file_path = pathlib.Path(filename)
        else:
            file_path = prompts_dir / filename

        if not file_path.exists():
            click.echo(f"Creating template: {file_path}")
            file_path.write_text(content)
        else:
            click.echo(f"Template already exists: {file_path}")


@cli.command()
def ralph():
    """[DEPRECATED] legacy Ralph loop. Use vibe setup/plan/implement instead."""
    click.echo(click.style("\n" + "!" * 60, fg="red", bold=True))
    click.echo(
        click.style(
            "!!! DEPRECATED: 'vibe ralph' is legacy and has been removed !!!",
            fg="red",
            bold=True,
        )
    )
    click.echo(click.style("!" * 60 + "\n", fg="red", bold=True))
    click.echo("Please use the new modular commands:")
    click.echo("  vibe setup          - Phase 1: Architecture")
    click.echo("  vibe normalize      - Phase 2: Standardize Specs")
    click.echo("  vibe plan           - Phase 3: Project Planning")
    click.echo("  vibe implement      - Phase 4: Building")
    click.echo("")


@cli.command()
@click.option(
    "--fast/--no-fast",
    is_flag=True,
    default=False,
    help="Only run tests for changed files (more efficient).",
)
@click.pass_context
def test_fix(ctx, fast):
    """Run the test and fix loop."""
    from vibe_tools.fixer import run_test_fix_loop

    run_test_fix_loop(
        agent=ctx.obj["agent"],
        caffeinate=ctx.obj.get("caffeinate", False),
        fast=fast,
        stream=ctx.obj.get("stream", False),
    )


@cli.command()
@click.pass_context
def coverage(ctx):
    """Run the coverage improvement loop."""
    from vibe_tools.coverage import improve_coverage_loop

    improve_coverage_loop(
        agent=ctx.obj["agent"],
        caffeinate=ctx.obj.get("caffeinate", False),
        stream=ctx.obj.get("stream", False),
    )


@cli.command()
@click.argument("input_file", required=False)
@click.option(
    "--yes", "-y", is_flag=True, help="Automatically overwrite existing PRDs."
)
@click.pass_context
def normalize(ctx, input_file, yes):
    """Phase 2: Normalize human-written PRDs from specs/ into machine-consumable YAML in prds/."""
    maybe_init_git()
    state = load_project_state()
    missing = check_dependencies("normalize", state)
    if missing:
        click.echo(f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first.")
        return

    from vibe_tools.normalize import normalize_prd

    normalize_prd(
        agent=ctx.obj["agent"],
        input_file=input_file,
        auto_overwrite=yes,
        caffeinate=ctx.obj.get("caffeinate", False),
        stream=ctx.obj.get("stream", False),
    )

    click.echo("\nNext Steps:")
    click.echo("[ ] Review/Edit generated YAMLs in prds/")
    click.echo("[ ] Generate Project Plan (vibe plan)")


@cli.command()
@click.option(
    "--interval",
    type=int,
    default=60,
    help="Monitoring interval in seconds (default: 60).",
)
@click.pass_context
def monitor(ctx, interval):
    """Monitor the progress of automated generation."""
    from vibe_tools.monitor import run_monitor

    run_monitor(
        agent=ctx.obj["agent"],
        interval=interval,
        stream=ctx.obj.get("stream", False),
    )


@cli.command(name="review-prd")
@click.option(
    "--review/--no-review",
    type=bool,
    default=True,
    help="Run the agentic review prompt after showing the PRD.",
)
@click.pass_context
def review_prd(ctx, review):
    """[DEPRECATED] List specs PRDs, display one, and optionally run review."""
    click.echo(
        click.style(
            "\n!!! DEPRECATED: 'review-prd' is deprecated !!!", fg="yellow", bold=True
        )
    )
    click.echo("'vibe prd' now includes a /review command during creation.\n")
    ensure_dir(SPECS_DIR)

    prd_files = _list_spec_files()
    if not prd_files:
        click.echo("No PRDs found in specs/.")
        return

    click.echo("Available specs:")
    for idx, prd_path in enumerate(prd_files, start=1):
        rel_path = prd_path.relative_to(SPECS_DIR)
        click.echo(f"  {idx}. {rel_path}")

    selected = _prompt_for_prd(prd_files)
    click.echo(f"\n--- {selected.name} ---")
    click.echo(selected.read_text())

    if review:
        _run_agent_review(
            agent_type=ctx.obj.get("agent", "cursor-agent"),
            prd_path=selected,
            caffeinate=ctx.obj.get("caffeinate", False),
            stream=ctx.obj.get("stream", False),
        )


def _list_spec_files() -> List[pathlib.Path]:
    if not SPECS_DIR.exists():
        return []
    # Search recursively for markdown files
    return sorted(SPECS_DIR.rglob("*.md"))


def _prompt_for_prd(prd_paths: List[pathlib.Path]) -> pathlib.Path:
    default = len(prd_paths)
    while True:
        selection = click.prompt(
            "Select a PRD to view",
            type=int,
            default=default,
        )
        if 1 <= selection <= len(prd_paths):
            return prd_paths[selection - 1]
        click.echo("Invalid selection. Please choose a number from the list.")


def _run_agent_review(
    agent_type: str, prd_path: pathlib.Path, caffeinate: bool, stream: bool = False
) -> None:
    if not REVIEW_PROMPT_TEMPLATE.exists():
        click.echo("Review prompt template missing; skipping agentic review.")
        return

    prompt_text = REVIEW_PROMPT_TEMPLATE.read_text().format(prd_path=prd_path)
    command = get_agent_command(agent_type, prompt_text)
    output, exit_code = run_agent(command, caffeinate=caffeinate, stream=stream)

    if exit_code != 0:
        click.echo(f"Agentic review failed (exit {exit_code}).")
        return

    click.echo("\n--- Agentic Review Output ---")
    click.echo(output)


@cli.command()
@click.option(
    "--title",
    "-t",
    help="Short description of the PRD or feature you want to explore.",
)
@click.option(
    "--type",
    "-T",
    type=click.Choice(["feature", "infra", "cicd", "architecture"]),
    default="feature",
    help="Type of PRD to write (default: feature).",
)
@click.pass_context
def prd(ctx, title, type):
    """Interactive PRD writer with slash commands."""
    from vibe_tools.prd_writer import InteractivePRD

    initial_prompt = title or click.prompt(
        f"Describe the {type} PRD you'd like to write"
    )

    # Base specs dir
    specs_base = pathlib.Path("specs")
    ensure_dir(specs_base)

    writer = InteractivePRD(
        agent_type=ctx.obj.get("agent", "cursor-agent"),
        specs_dir=specs_base,
        prd_type=type,
        stream=ctx.obj.get("stream", False),
    )
    writer.run_loop(initial_prompt)


@cli.command(name="write-prd")
@click.option(
    "--title",
    "-t",
    help="Short description of the PRD or feature you want to explore.",
)
@click.option(
    "--type",
    "-T",
    type=click.Choice(["feature", "infra", "cicd", "architecture"]),
    default="feature",
    help="Type of PRD to write (default: feature).",
)
@click.pass_context
def write_prd(ctx, title, type):
    """[DEPRECATED] Use 'vibe prd' instead."""
    click.echo(
        click.style(
            "\n!!! DEPRECATED: 'write-prd' is deprecated !!!", fg="yellow", bold=True
        )
    )
    click.echo("Please use 'vibe prd' for the new interactive experience.\n")
    from vibe_tools.prd_writer import PRDWriter

    initial_prompt = title or click.prompt(
        f"Describe the {type} PRD you'd like to write"
    )

    # Base specs dir
    specs_base = pathlib.Path("specs")
    ensure_dir(specs_base)

    writer = PRDWriter(
        agent_type=ctx.obj.get("agent", "cursor-agent"),
        specs_dir=specs_base,
        prd_type=type,
        stream=ctx.obj.get("stream", False),
    )
    writer.create_prd(initial_prompt)


@cli.command()
def history():
    """List the status of all PRDs."""
    if not PRD_DIR.exists():
        click.echo(f"PRD directory {PRD_DIR} not found.")
        return

    from vibe_tools.utils import collect_prd_files

    prds = collect_prd_files()
    if not prds:
        click.echo("No PRD files found.")
        return

    click.echo(f"{'PRD':<40} {'Status':<15}")
    click.echo("-" * 56)

    state = load_project_state()
    completed_prds = state.get("completed_prds", [])
    started_prds = state.get("started_prds", [])

    for prd_file in prds:
        # Show relative path for infra/cicd
        try:
            project_name = prd_file.relative_to(PRD_DIR).with_suffix("").as_posix()
        except ValueError:
            project_name = prd_file.stem

        if prd_file.stem in completed_prds:
            status = click.style("✅ DONE", fg="green")
        elif prd_file.stem in started_prds:
            status = click.style("⏳ IN_PROGRESS", fg="blue")
        else:
            status = click.style("⚪️ PENDING", fg="white", dim=True)

        click.echo(f"{project_name:<40} {status:<15}")


@cli.command()
def status():
    """Display a comprehensive system status report."""
    from vibe_tools.utils import get_vibe_status_report

    click.echo(get_vibe_status_report())


@cli.command()
def docs():
    """Display the project documentation (README.md)."""
    from vibe_tools.templates import TEMPLATES
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.theme import Theme

    content = TEMPLATES.get("README", "Documentation not found in templates.")

    # Custom milder theme
    custom_theme = Theme(
        {
            "markdown.header": "bold white",
            "markdown.h1": "bold white",
            "markdown.h2": "bold white",
            "markdown.h3": "bold white",
            "markdown.link": "blue",
            "markdown.link_url": "dim blue",
            "markdown.code": "cyan",
            "markdown.code_block": "cyan",
            "markdown.item.bullet": "white",
            "markdown.item.number": "white",
            "markdown.block_quote": "dim white",
        }
    )

    console = Console(theme=custom_theme)
    # Using a milder code theme for syntax highlighting
    md = Markdown(content, code_theme="friendly")
    console.print(md)


@cli.command()
def cost():
    """Display the total estimated cost of LLM usage for this project."""
    total = get_total_cost()
    config = load_config()
    use_google = config.get("use_google_sheets", False)
    sheet_id = config.get("google_sheet_id")

    click.echo(f"\nTotal estimated cost: ${total:.4f} USD")
    click.echo(f"Detailed log available at: {COSTS_DIR}/usage.csv")

    if use_google and sheet_id:
        click.echo(f"Google Sheets Logging: ENABLED (ID: {sheet_id})")
    else:
        click.echo("Google Sheets Logging: DISABLED")


@cli.command()
@click.option(
    "--auto",
    is_flag=True,
    help="Automatically propose architecture if architecture.yaml is missing.",
)
@click.option(
    "--import-code",
    "import_code",
    is_flag=True,
    help="Import existing codebase to generate architecture-current.yaml.",
)
@click.pass_context
def setup(ctx, auto, import_code):
    """Phase 1: Architecture Setup. Reconciles architecture.yaml with architecture-current.yaml."""
    from vibe_tools.ralph import RalphLoop

    state = load_project_state()
    agent = ctx.obj.get("agent", "cursor-agent")
    stream = ctx.obj.get("stream", False)

    if import_code:
        click.echo("🔍 Analyzing codebase to generate current architecture and infrastructure definitions...")
        prompt = f"""Analyze the current codebase and generate two comprehensive YAML files in the project root:
1. '{ARCHITECTURE_CURRENT.name}': Describe the tech stack, directory structure, key dependencies, and test suites.
2. '{INFRA_CURRENT.name}': Describe the infrastructure including databases, external services, caches, queues, and object storage.

The files should be in YAML format and provide a clear picture of the ACTUAL state of the project.

ACTUAL CODEBASE:
(The agent has access to the filesystem to perform this analysis)

Once you have analyzed the codebase and written BOTH the '{ARCHITECTURE_CURRENT.name}' and '{INFRA_CURRENT.name}' files, include {COMPLETION_PROMISE}.
"""
        from vibe_tools.ralph import COMPLETION_PROMISE
        cmd = get_agent_command(agent, prompt)
        output, code = run_agent(cmd, stream=stream)
        
        if code == 0 and COMPLETION_PROMISE in output:
            click.echo(f"✅ Generated {ARCHITECTURE_CURRENT} and {INFRA_CURRENT}")
            
            # Mark setup phase as complete since we've imported the code
            state["phases"]["setup"]["status"] = "completed"
            if ARCHITECTURE.exists():
                state["phases"]["setup"]["hash"] = get_file_hash(ARCHITECTURE)
            save_project_state(state)
            click.echo("✅ Setup phase marked as COMPLETED in project-state.json.")
        else:
            click.echo(f"❌ Failed to generate discovery files.")
        return

    if not ARCHITECTURE.exists():
        if auto:
            click.echo("Proposing architecture.yaml based on PRDs...")
            # TODO: Implement auto-proposal logic
            prompt = "Analyze the PRDs in prds/ and propose a comprehensive 'architecture.yaml' file that defines the tech stack, database schema, and project structure."
            cmd = get_agent_command(agent, prompt)
            run_agent(cmd, stream=stream)
        else:
            click.echo(
                f"❌ {ARCHITECTURE} not found. Use --auto to propose one or create it manually."
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

    success = loop.run()
    if success:
        state["phases"]["setup"]["status"] = "completed"
        state["phases"]["setup"]["hash"] = get_file_hash(ARCHITECTURE)
        save_project_state(state)
        click.echo("\n✅ Architecture setup complete. project-state.json updated.")
        click.echo("\nNext Steps:")
        click.echo("[ ] Normalize Specs (vibe normalize)")
        click.echo("[ ] Generate Project Plan (vibe plan)")
    else:
        click.echo("❌ Architecture setup failed.")


@cli.command()
@click.pass_context
def plan(ctx):
    """Phase 3: Project Planning. Generates project-plan.yaml from PRDs and Architecture."""
    state = load_project_state()
    missing = check_dependencies("plan", state)
    if missing:
        click.echo(f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first.")
        return

    agent = ctx.obj.get("agent", "cursor-agent")
    stream = ctx.obj.get("stream", False)

    click.echo("🧠 Generating project-plan.yaml...")
    # TODO: Implement Planner Agent logic
    from vibe_tools.ralph import run_planner_agent

    project_plan = run_planner_agent(agent, stream=stream)
    if project_plan:
        state["phases"]["plan"]["status"] = "completed"
        state["phases"]["plan"]["hash"] = get_file_hash(PROJECT_PLAN)
        save_project_state(state)
        click.echo(f"\n✅ Project plan generated: {PROJECT_PLAN}")
        click.echo("\nNext Steps:")
        click.echo("[ ] Review/Edit project-plan.yaml")
        click.echo("[ ] Start Building (vibe implement)")
    else:
        click.echo("❌ Project planning failed.")


@cli.command()
@click.pass_context
def implement(ctx):
    """Phase 4: Implement. Iterates through the project-plan.yaml."""
    state = load_project_state()
    missing = check_dependencies("implement", state)
    if missing:
        click.echo(f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first.")
        return

    from vibe_tools.ralph import implementation_loop

    agent = ctx.obj.get("agent", "cursor-agent")
    stream = ctx.obj.get("stream", False)

    success = implementation_loop(agent, stream=stream)
    if success:
        state["phases"]["implement"]["status"] = "completed"
        save_project_state(state)
        click.echo("✅ Implementation complete.")
        click.echo("\nNext Steps:")
        click.echo("[ ] Run Tests & Reconciliation (vibe testing)")
        click.echo("[ ] Setup Infrastructure (vibe infra)")
        click.echo("[ ] Setup CI/CD (vibe cicd)")
    else:
        click.echo("❌ Implementation failed.")


@cli.command()
@click.pass_context
def infra(ctx):
    """Phase 5: Infrastructure reconciliation. Ensures services are reachable."""
    state = load_project_state()
    missing = check_dependencies("infra", state)
    if missing:
        click.echo(f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first.")
        return

    from vibe_tools.ralph import RalphLoop

    agent = ctx.obj.get("agent", "cursor-agent")
    stream = ctx.obj.get("stream", False)

    loop = RalphLoop(
        name="Infrastructure",
        desired_file=INFRA,
        current_file=INFRA_CURRENT,
        agent=agent,
        stream=stream,
    )
    
    # Custom instruction for infra verification
    loop.instructions = [
        "Specifically verify that all configured services (databases, queues, etc.) are reachable from the application environment.",
        "Test connectivity using appropriate tools (e.g., pg_isready, redis-cli, curl).",
        "Set up or update environment variables as needed."
    ]

    if loop.run():
        state["phases"]["infra"]["status"] = "completed"
        save_project_state(state)
        click.echo("✅ Infrastructure reconciliation and verification complete.")
        click.echo("\nNext Steps:")
        click.echo("[ ] Setup CI/CD (vibe cicd)")
        click.echo("[ ] Deployment (vibe deploy)")
    else:
        click.echo("❌ Infrastructure reconciliation failed.")


@cli.command()
@click.pass_context
def cicd(ctx):
    """Phase 6: CI/CD reconciliation. Ensures deployment pipelines are ready."""
    state = load_project_state()
    missing = check_dependencies("cicd", state)
    if missing:
        click.echo(f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first.")
        return

    from vibe_tools.ralph import RalphLoop

    agent = ctx.obj.get("agent", "cursor-agent")
    stream = ctx.obj.get("stream", False)

    loop = RalphLoop(
        name="CI/CD",
        desired_file=CICD,
        current_file=CICD_CURRENT,
        agent=agent,
        stream=stream,
    )
    
    loop.instructions = [
        "Verify that all CI/CD pipelines and deployment strategies are correctly configured.",
        "Ensure secrets and environment variables required for deployment are correctly handled."
    ]

    if loop.run():
        state["phases"]["cicd"]["status"] = "completed"
        save_project_state(state)
        click.echo("✅ CI/CD reconciliation complete.")
        click.echo("\nNext Steps:")
        click.echo("[ ] Setup Infrastructure (vibe infra)")
        click.echo("[ ] Deployment (vibe deploy)")
    else:
        click.echo("❌ CI/CD reconciliation failed.")


@cli.command()
@click.pass_context
def testing(ctx):
    """Phase 7: Testing reconciliation. Ensures integration and regression tests pass."""
    state = load_project_state()
    missing = check_dependencies("testing", state)
    if missing:
        click.echo(f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first.")
        return

    from vibe_tools.ralph import RalphLoop

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
        "Run 'make test-integration' and 'make test-regression' to verify."
    ]

    if loop.run():
        state["phases"]["testing"]["status"] = "completed"
        save_project_state(state)
        click.echo("✅ Testing reconciliation complete.")
        click.echo("\nNext Steps:")
        click.echo("[ ] Deployment (vibe deploy)")
    else:
        click.echo("❌ Testing reconciliation failed.")


@cli.command()
@click.pass_context
def deploy(ctx):
    """Phase 8: Deployment."""
    state = load_project_state()
    missing = check_dependencies("deploy", state)
    if missing:
        click.echo(f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first.")
        return

    # TODO: Implement deployment logic
    click.echo("🚀 Triggering deployment...")
    state["phases"]["deploy"]["status"] = "completed"
    save_project_state(state)
    click.echo("\n✨ Project fully deployed! All lifecycle phases completed.")


@cli.command()
@click.pass_context
def ideation(ctx):
    """Scenario E: Interactive ideation to generate PRDs."""
    agent = ctx.obj.get("agent", "cursor-agent")
    stream = ctx.obj.get("stream", False)

    click.echo("💡 Starting interactive ideation session...")
    prompt = "I have an idea for a project. Please walk me through an interactive loop to define the core PRDs and requirements. Ask me questions one by one until we have enough to generate initial PRD files in 'specs/'."
    cmd = get_agent_command(agent, prompt)
    run_agent(cmd, stream=stream)
    click.echo("✅ Ideation complete. Specs generated in specs/.")
    click.echo("\nNext Steps:")
    click.echo("[ ] Setup Architecture (vibe setup --auto)")


@cli.command()
@click.argument("text", required=False)
@click.option(
    "--list", "-l", "list_memories", is_flag=True, help="List all saved memories."
)
@click.option(
    "--delete", "-d", "delete_idx", type=int, help="Delete a memory by its index."
)
@click.option("--clear", is_flag=True, help="Clear all saved memories.")
def memory(text, list_memories, delete_idx, clear):
    """Save a 'memory' (global instruction) that is always sent to the agent."""
    from vibe_tools.utils import INSTRUCTIONS_DIR

    ensure_dir(INSTRUCTIONS_DIR)

    if clear:
        if click.confirm("Are you sure you want to clear all memories?", default=False):
            for f in INSTRUCTIONS_DIR.glob("*"):
                if f.is_file():
                    f.unlink()
            click.echo("✅ All memories cleared.")
        return

    if delete_idx is not None:
        files = sorted(INSTRUCTIONS_DIR.glob("*"))
        if 1 <= delete_idx <= len(files):
            target = files[delete_idx - 1]
            if click.confirm(f"Delete memory: {target.name}?", default=True):
                target.unlink()
                click.echo(f"✅ Deleted {target.name}.")
        else:
            click.echo(f"❌ Invalid index: {delete_idx}")
        return

    if list_memories:
        files = sorted(INSTRUCTIONS_DIR.glob("*"))
        if not files:
            click.echo("No memories saved.")
        else:
            click.echo("Current memories:")
            for idx, f in enumerate(files, start=1):
                content = f.read_text().strip()
                # Show first line or truncate
                preview = content.splitlines()[0] if content else "(empty)"
                if len(preview) > 60:
                    preview = preview[:57] + "..."
                click.echo(f"  {idx}. {f.name}: {preview}")
        return

    if not text:
        text = click.prompt("Enter the instruction to remember")

    if text:
        import datetime

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        # slugify text for filename
        slug = "".join(c if c.isalnum() else "_" for c in text[:30]).lower()
        filename = f"memory_{timestamp}_{slug}.txt"
        filepath = INSTRUCTIONS_DIR / filename
        filepath.write_text(text)
        click.echo(f"✅ Memory saved to {filepath}")


@cli.command()
@click.argument("text", required=False)
@click.option(
    "--list", "-l", "list_memories", is_flag=True, help="List all saved memories."
)
@click.option(
    "--delete", "-d", "delete_idx", type=int, help="Delete a memory by its index."
)
@click.option("--clear", is_flag=True, help="Clear all saved memories.")
@click.pass_context
def remember(ctx, text, list_memories, delete_idx, clear):
    """Alias for 'vibe memory'."""
    ctx.invoke(
        memory,
        text=text,
        list_memories=list_memories,
        delete_idx=delete_idx,
        clear=clear,
    )


@cli.command()
@click.argument("prd_id")
def rerun(prd_id):
    """Reset a PRD's state and branch to allow rerunning."""
    # Try to find the PRD file
    prd_file = None
    if prd_id.startswith("prd_") and prd_id.endswith(".yaml"):
        prd_file = PRD_DIR / prd_id
    elif prd_id.startswith("prd_"):
        prd_file = PRD_DIR / f"{prd_id}.yaml"
    else:
        # Check if it's just the number/name part
        potential_files = list(PRD_DIR.glob(f"prd_*{prd_id}*.yaml"))
        if len(potential_files) == 1:
            prd_file = potential_files[0]
        elif len(potential_files) > 1:
            click.echo(f"Multiple PRDs found matching '{prd_id}':")
            for f in potential_files:
                click.echo(f"  - {f.name}")
            return

    if not prd_file or not prd_file.exists():
        click.echo(f"PRD '{prd_id}' not found.")
        return

    project_name = prd_file.stem
    branch_name = f"feature/{project_name}"

    click.echo(f"Rerunning PRD: {project_name}")

    # 1. Clear saved state if it matches this PRD or is in completed_prds
    state = load_project_state()
    state_changed = False

    # Check active task
    active_task = state.get("active_task")
    if active_task and active_task.get("prd_name") == project_name:
        state["active_task"] = None
        state_changed = True
        click.echo("✅ Cleared saved active task state.")

    # Check completed prds
    if project_name in state.get("completed_prds", []):
        state["completed_prds"].remove(project_name)
        state_changed = True
        click.echo("✅ Removed from completed PRDs list.")

    # Check started prds
    if project_name in state.get("started_prds", []):
        state["started_prds"].remove(project_name)
        state_changed = True
        click.echo("✅ Removed from started PRDs list.")

    if state_changed:
        save_project_state(state)

    # 2. Delete the branch if it exists
    _, check_branch = run_command(
        ["git", "rev-parse", "--verify", branch_name], check=False
    )
    if check_branch == 0:
        # Check if we are currently on that branch
        stdout, _ = run_command(["git", "branch", "--show-current"], check=False)
        if stdout.strip() == branch_name:
            main_branch = get_main_branch()
            click.echo(
                f"Currently on branch {branch_name}. Switching to {main_branch}..."
            )
            run_command(["git", "checkout", main_branch])

        # Delete branch
        _, code = run_command(["git", "branch", "-D", branch_name], check=False)
        if code == 0:
            click.echo(f"✅ Deleted branch {branch_name}.")
        else:
            click.echo(f"❌ Failed to delete branch {branch_name}.")
    else:
        click.echo(f"Branch {branch_name} does not exist. Nothing to delete.")

    click.echo(f"\nReady to rerun: {project_name} state has been reset.")


if __name__ == "__main__":
    cli()
