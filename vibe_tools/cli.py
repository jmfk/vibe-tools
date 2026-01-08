import atexit
import datetime
import json
import logging
import pathlib
import subprocess
from typing import List

import click
import yaml


class OrderedGroup(click.Group):
    """Custom Click Group to order commands in the help menu."""

    def list_commands(self, ctx: click.Context) -> List[str]:
        # Define the desired order of commands
        order = [
            # Phases 1-8
            "architect",
            "pm",
            "normalize",
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
            "remember",
            "monitor",
            "rerun",
            "implemented",
            "ps",
            "kill",
            "test-fix",
            "coverage",
            "branch",
            "branches",
            "branch-resolve",
            "billing-groups",
            "demo-data",
            "init",
            # Deprecated
            "ralph",
            "prd",
            "review-prd",
            "write-prd",
        ]

        # Get the actual commands available
        commands = super().list_commands(ctx)

        # Order the commands based on the defined order, putting any unknown commands at the end
        ordered_commands = [cmd for cmd in order if cmd in commands]
        other_commands = sorted([cmd for cmd in commands if cmd not in order])

        return ordered_commands + other_commands


from dotenv import find_dotenv, load_dotenv

from vibe_tools.cost import finalize_cost_report, get_total_cost
from vibe_tools.setup import SERVICE_DEFINITIONS, install_deps, maybe_init_git
from vibe_tools.templates import TEMPLATES
from vibe_tools.utils import (
    ARCHITECTURE,
    ARCHITECTURE_CURRENT,
    ARCHITECTURE_SPEC,
    BUILD,
    BUILD_CURRENT,
    BUILD_SPEC,
    CICD,
    CICD_CURRENT,
    CICD_SPEC,
    COSTS_DIR,
    INFRA,
    INFRA_CURRENT,
    INFRA_SPEC,
    PRD_DIR,
    TESTING_CONFIG,
    TESTING_CURRENT,
    TESTING_SPEC,
    VIBE_PROJECT_DIR,
    check_dependencies,
    cleanup_stale_processes,
    collect_prd_files,
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
    load_config,
    load_project_state,
    logger,
    reset_prd_state,
    run_agent,
    run_command,
    save_config,
    save_project_state,
    setup_logging,
)

# Load environment variables from .env file at startup
load_dotenv(find_dotenv() or ".env")

CONFIG_FILE = pathlib.Path(".vibe_config.json")
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
    default=True,
    help="Output verbose information (like prompts) to the terminal.",
)
@click.option(
    "--stream/--no-stream",
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

    # Ensure files are in the right place
    from vibe_tools.utils import migrate_to_project_dir

    migrate_to_project_dir()

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
            pathlib.Path("specs")
            if pathlib.Path("specs").exists()
            else pathlib.Path("spec")
        )
        click.echo(
            f"  Specs Directory: {specs_dir if specs_dir.exists() else 'Not found (defaults to specs/)'}"
        )

        if not project_init:
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
    click.echo(
        click.style("\n=== VIBE PROJECT INITIALIZATION ===", fg="cyan", bold=True)
    )
    click.echo("Welcome! Let's get your project set up for automated development.\n")

    click.echo("Please select your starting scenario:")
    click.echo(
        click.style("  A) Human Specs", bold=True)
        + " - You already have human-written markdown specs in 'specs/'."
    )
    click.echo(
        click.style("  B) Adoption", bold=True)
        + " - You have an existing codebase and want Vibe to discover it."
    )
    click.echo(
        click.style("  C) Architecture Ready", bold=True)
        + " - You have an 'architecture.yaml' ready to go."
    )
    click.echo(
        click.style("  D) Manual Setup", bold=True)
        + " - Just initialize the folders and templates for manual work."
    )

    choice = click.prompt(
        "\nSelect scenario",
        type=click.Choice(["A", "B", "C", "D"], case_sensitive=False),
        default="D",
    ).upper()

    # Always perform basic initialization first
    _perform_basic_init()

    if choice == "A":
        click.echo(
            "\n📄 Basic initialization complete. Your human specs should be in 'specs/'."
        )
    elif choice == "B":
        click.echo("\n🔍 Starting codebase discovery...")
        ctx.invoke(setup, import_code=True)
    elif choice == "C":
        click.echo("\n🏗️  Basic initialization complete. 'architecture.yaml' is ready.")
    else:
        click.echo("\n✅ Basic initialization complete.")

    click.echo("\nNext Steps:")
    click.echo(
        f"  {click.style('vibe architect', fg='cyan'):<20} Phase 1: Refine architecture and infrastructure"
    )
    click.echo(
        f"  {click.style('vibe pm', fg='magenta'):<20} Phase 1: Refine PRDs and product specs"
    )
    click.echo(
        f"  {click.style('vibe normalize', fg='yellow'):<20} Phase 2: Standardize all specs into machine-readable YAML"
    )
    click.echo("\nRun 'vibe status' at any time to see your project progress.")


def _perform_basic_init():
    """Helper to initialize the project structure and essential templates."""
    maybe_init_git()

    from vibe_tools.utils import (
        COSTS_DIR,
        INSTRUCTIONS_DIR,
        LOGS_DIR,
        PRD_DIR,
        VIBE_DATA_DIR,
        VIBE_PROJECT_DIR,
        ensure_dir,
        ensure_project_structure,
        migrate_to_project_dir,
    )

    # First, migrate any existing files from root to project/
    migrate_to_project_dir()

    # Ensure structure exists
    ensure_project_structure()

    ensure_dir(VIBE_PROJECT_DIR)
    ensure_gitignore(str(VIBE_PROJECT_DIR) + "/")

    # Create new directories for instructions and specs
    ensure_dir(INSTRUCTIONS_DIR)
    ensure_dir(pathlib.Path("specs"))
    ensure_dir(PRD_DIR)
    ensure_dir(LOGS_DIR)
    ensure_dir(COSTS_DIR)
    ensure_dir(VIBE_DATA_DIR)

    # Only create Makefile if it doesn't exist
    if "Makefile" in TEMPLATES:
        makefile_path = pathlib.Path("Makefile")
        if not makefile_path.exists():
            click.echo(f"Creating template: {makefile_path}")
            makefile_path.write_text(TEMPLATES["Makefile"])
        else:
            click.echo(f"Template already exists: {makefile_path}")


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
    click.echo("  vibe architect      - Phase 1: Architecture")
    click.echo("  vibe pm             - Phase 1: PRDs")
    click.echo("  vibe normalize      - Phase 2: Standardize Specs")
    click.echo("  vibe setup          - Phase 3: Architecture Setup")
    click.echo("  vibe implement      - Phase 5: Building")
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
@click.argument("input_files", nargs=-1, required=False)
@click.option(
    "--yes", "-y", is_flag=True, help="Automatically overwrite existing PRDs."
)
@click.option(
    "--debug", is_flag=True, help="Output all prompts and results for debugging."
)
@click.pass_context
def normalize(ctx, input_files, yes, debug):
    """Phase 2: Normalize human-written PRDs from specs/ into machine-consumable YAML in prds/."""
    maybe_init_git()
    state = load_project_state()
    missing = check_dependencies("normalize", state)
    if missing:
        click.echo(
            f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first."
        )
        return

    from vibe_tools.normalize import normalize_prd

    # Map special file names to their spec paths
    special_files = {
        "infrastructure": INFRA_SPEC,
        "architecture": ARCHITECTURE_SPEC,
        "cicd": CICD_SPEC,
        "testing": TESTING_SPEC,
        "build": BUILD_SPEC,
        "project-overview": pathlib.Path("specs/project-overview.md"),
        "project_overview": pathlib.Path("specs/project-overview.md"),
    }

    # Process input files: map special names and resolve paths
    if input_files:
        files_to_normalize = []
        for input_file in input_files:
            # Remove .md extension if present for matching
            file_key = input_file.replace(".md", "").lower()

            if file_key in special_files:
                # Use the mapped spec file path
                files_to_normalize.append(str(special_files[file_key]))
            else:
                # Use as-is (normalize_prd will check if it exists)
                files_to_normalize.append(input_file)

        click.echo("🔄 Normalizing specs...")
        for file_to_normalize in files_to_normalize:
            normalize_prd(
                agent=ctx.obj["agent"],
                input_file=file_to_normalize,
                auto_overwrite=yes,
                caffeinate=ctx.obj.get("caffeinate", False),
                stream=ctx.obj.get("stream", False),
                debug=debug,
            )
    else:
        # No files specified, normalize all files in specs/
        click.echo("🔄 Normalizing specs...")
        normalize_prd(
            agent=ctx.obj["agent"],
            input_file=None,
            auto_overwrite=yes,
            caffeinate=ctx.obj.get("caffeinate", False),
            stream=ctx.obj.get("stream", False),
            debug=debug,
        )

    click.echo("\nNext Steps:")
    click.echo("[ ] Review/Edit generated YAMLs in project/prds/")
    click.echo("[ ] Architecture Setup (vibe setup)")
    click.echo("[ ] Install Dependencies (vibe deps)")
    click.echo("[ ] Start Building (vibe implement)")


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
    try:
        prompt_template = get_prompt("review_prompt.txt")
    except FileNotFoundError:
        click.echo("Review prompt template missing; skipping agentic review.")
        return

    prompt_text = prompt_template.format(prd_path=prd_path)
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
    """[DEPRECATED] Use 'vibe pm' instead. Interactive PRD writer with slash commands."""
    click.echo(
        click.style("\n!!! DEPRECATED: 'prd' is deprecated !!!", fg="yellow", bold=True)
    )
    click.echo("Please use 'vibe pm' for the newer interactive experience.\n")
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
    from vibe_tools.utils import collect_all_prd_info, load_project_state

    prds = collect_all_prd_info()
    if not prds:
        click.echo("No PRD files found.")
        return

    click.echo(f"{'PRD':<40} {'MD':<5} {'YAML':<5} {'Status':<15}")
    click.echo("-" * 70)

    state = load_project_state()
    completed_prds = state.get("completed_prds", [])
    started_prds = state.get("started_prds", [])

    for info in prds:
        project_name = info["name"]

        # We need the actual stem used in state.json (which is usually prd_name or the yaml stem)
        # The project state stores names like '01_pm_prd_focus' or 'prd_01_pm_prd_focus'
        # Let's check both the clean name and the prd_ prefixed name
        prd_stem = project_name
        if info["has_yaml"] and info["yaml_path"]:
            prd_stem = info["yaml_path"].stem
        elif info["has_md"] and info["md_path"]:
            # If only MD exists, it's definitely pending/started by its stem or clean name
            prd_stem = info["md_path"].stem

        md_status = "✅" if info["has_md"] else "❌"
        yaml_status = "✅" if info["has_yaml"] else "❌"

        if prd_stem in completed_prds or project_name in completed_prds:
            status = click.style("✅ DONE", fg="green")
        elif prd_stem in started_prds or project_name in started_prds:
            status = click.style("⏳ IN_PROGRESS", fg="blue")
        else:
            status = click.style("⚪️ PENDING", fg="white", dim=True)

        click.echo(f"{project_name:<40} {md_status:<5} {yaml_status:<5} {status:<15}")


@cli.command()
def status():
    """Display a comprehensive system status report."""
    from vibe_tools.utils import get_vibe_status_report

    click.echo(get_vibe_status_report())


@cli.command()
def docs():
    """Display the project documentation (README.md)."""
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.theme import Theme

    from vibe_tools.templates import TEMPLATES

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
    "--import-code",
    "import_code",
    is_flag=True,
    help="Import existing codebase to generate architecture-current.yaml.",
)
@click.pass_context
def setup(ctx, import_code):
    """Phase 3: Architecture Setup. Reconciles architecture.yaml with architecture-current.yaml."""
    from vibe_tools.ralph import RalphLoop

    state = load_project_state()
    agent = ctx.obj.get("agent", "cursor-agent")
    stream = ctx.obj.get("stream", False)

    if import_code:
        from vibe_tools.ralph import COMPLETION_PROMISE
        from vibe_tools.utils import ensure_project_structure

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
        "Create dummy test files (e.g., backend/tests/test_initial.py, frontend/src/initial.test.ts) to verify the harness.",
        "Ensure test dependencies and scripts are present in pyproject.toml and package.json.",
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

        click.echo("\nNext Steps:")
        click.echo("1. Run 'vibe deps' to install any new testing dependencies.")
        click.echo("2. Start Building (vibe implement)")
    else:
        click.echo("❌ Architecture setup failed.")


@cli.command()
def deps():
    """Phase 4: Install required Python and Frontend dependencies."""
    install_deps()
    click.echo("✅ Dependencies installed.")


@cli.command()
@click.argument("query", required=False)
@click.pass_context
def architect(ctx, query):
    """Phase 1: Interactive architecture and infrastructure spec manager."""
    from vibe_tools.architect import InteractiveArchitect

    architect_tool = InteractiveArchitect(
        agent_type=ctx.obj.get("agent", "cursor-agent"),
        stream=ctx.obj.get("stream", True),
    )
    architect_tool.run_loop(query)


@cli.command()
@click.argument("query", required=False)
@click.pass_context
def pm(ctx, query):
    """Phase 1: Interactive PRD and specification manager."""
    from vibe_tools.pm import InteractivePM

    pm_tool = InteractivePM(
        agent_type=ctx.obj.get("agent", "cursor-agent"),
        stream=ctx.obj.get("stream", True),
    )
    pm_tool.run_loop(query)


@cli.command()
@click.pass_context
def implement(ctx):
    """Phase 5: Implement. Iterates through implementation plans defined in state.json."""
    state = load_project_state()
    missing = check_dependencies("implement", state)
    if missing:
        click.echo(
            f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first."
        )
        return

    from vibe_tools.utils import collect_prd_files

    if not collect_prd_files():
        click.echo("❌ No machine-readable PRD YAMLs found in project/prds/.")
        click.echo(
            "   Run 'vibe pm' to refine specs and 'vibe normalize' to generate them."
        )
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
    else:
        click.echo("❌ Implementation failed.")


@cli.command()
@click.pass_context
def build(ctx):
    """Build system reconciliation. Ensures the build system builds all parts and they can start."""
    state = load_project_state()
    missing = check_dependencies("implement", state)
    if missing:
        click.echo(
            f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first."
        )
        return

    # Handle missing build files
    if not BUILD.exists():
        if BUILD_SPEC.exists():
            # build.md exists but not normalized - auto-normalize it
            click.echo(f"📝 {BUILD_SPEC} found but not normalized. Normalizing...")
            from vibe_tools.normalize import normalize_prd

            normalize_prd(
                agent=ctx.obj.get("agent", "cursor-agent"),
                input_file=str(BUILD_SPEC),
                auto_overwrite=True,
                caffeinate=ctx.obj.get("caffeinate", False),
                stream=ctx.obj.get("stream", False),
            )
            if not BUILD.exists():
                click.echo(
                    "❌ Normalization failed. Please review and fix build.md, then run 'vibe normalize' manually."
                )
                return
            click.echo("✅ Build specification normalized successfully.")
        else:
            # Neither exists - generate from architecture.md
            if not ARCHITECTURE_SPEC.exists():
                click.echo(
                    f"❌ {ARCHITECTURE_SPEC} not found. Please create it first using 'vibe architect'."
                )
                return

            click.echo(
                "📋 Build specification not found. Generating from architecture.md..."
            )
            agent = ctx.obj.get("agent", "cursor-agent")
            stream = ctx.obj.get("stream", False)

            # Read architecture.md
            arch_content = ARCHITECTURE_SPEC.read_text()

            # Generate build.md using agent
            prompt = f"""You are generating a build specification based on the architecture.

Analyze the architecture and create a comprehensive build.md file that specifies:
- How to build each application part (backend, frontend, etc.)
- Build dependencies and requirements
- Build commands and scripts
- Development environment setup
- How to start the application in development mode
- Build artifacts and outputs
- Services that need to be started for development

IMPORTANT REQUIREMENTS:
1. **Makefile Targets**: ALWAYS include a comprehensive set of Makefile targets for:
   - Building: `make build`, `make build-backend`, `make build-frontend`
   - Testing: `make test`, `make test-backend`, `make test-frontend`
   - Development: `make dev`, `make dev-start`, `make dev-stop`, `make dev-restart`
   - Linting: `make lint`, `make lint-backend`, `make lint-frontend`
   - Coverage: `make coverage`, `make coverage-backend`, `make coverage-frontend`
   - Cleanup: `make clean`, `make clean-backend`, `make clean-frontend`

2. **Skaffold and Helm**: If the architecture uses Kubernetes or container orchestration:
   - Include Skaffold configuration for local Kubernetes development
   - Include Helm charts for deployment
   - Document how to use `skaffold dev` for local development
   - Document Helm chart structure and values

3. **Services Section**: Clearly list all services/components that need to run in development mode with their startup commands.

The architecture specification is in specs/architecture.md:

{arch_content}

Generate a complete build.md file following this structure:

# Build Specification

## 1. Overview
[High-level overview of the build system and how different parts are built. Mention if using Skaffold/Helm for Kubernetes-based development.]

## 2. Build Components
[For each component (backend, frontend, etc.), specify:
- Build commands
- Dependencies
- Build outputs/artifacts
- How to verify the build succeeded]

## 3. Development Environment

### 3.1 Services Required
[List all services that must be running for development (PostgreSQL, Redis, etc.)]

### 3.2 Environment Variables
[Required environment variables and .env file setup]

### 3.3 Startup Commands
[Detailed startup commands for each service/component. Include both manual commands and Makefile targets.]

### 3.4 Verification
[How to verify the development environment is running correctly]

## 4. Build System

### 4.1 Makefile Targets
[COMPREHENSIVE list of all Makefile targets. MUST include:
- Build targets: build, build-backend, build-frontend
- Test targets: test, test-backend, test-frontend, test-integration
- Development targets: dev, dev-start, dev-stop, dev-restart
- Lint targets: lint, lint-backend, lint-frontend
- Coverage targets: coverage, coverage-backend, coverage-frontend
- Clean targets: clean, clean-backend, clean-frontend
- Install targets: install, install-backend, install-frontend]

### 4.2 Container Orchestration
[If using Kubernetes:
- Skaffold configuration and usage (`skaffold dev`, `skaffold run`)
- Helm chart structure and deployment
- Local cluster setup (Minikube/Kind) instructions]

### 4.3 Docker Builds
[Docker build commands and Dockerfile locations if applicable]

### 4.4 CI/CD Build Steps
[CI/CD pipeline steps and automation]

Output ONLY the markdown content for build.md, starting with the title and ending with the last section. Do not include code fences or explanations.
"""

            cmd = get_agent_command(agent, prompt)
            output, code = run_agent(cmd, stream=stream)

            if code != 0 or not output.strip():
                click.echo(
                    "❌ Failed to generate build.md. Please create it manually using 'vibe architect'."
                )
                return

            # Clean output (remove code fences if present)
            clean_output = output.strip()
            if clean_output.startswith("```"):
                lines = clean_output.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_output = "\n".join(lines).strip()

            # Write build.md
            ensure_dir(BUILD_SPEC.parent)
            BUILD_SPEC.write_text(clean_output)
            click.echo(f"✅ Generated {BUILD_SPEC}")
            click.echo(
                "📝 Please review the generated build.md, then it will be normalized automatically."
            )

            # Auto-normalize
            click.echo("🔄 Normalizing build.md...")
            from vibe_tools.normalize import normalize_prd

            normalize_prd(
                agent=agent,
                input_file=str(BUILD_SPEC),
                auto_overwrite=True,
                caffeinate=ctx.obj.get("caffeinate", False),
                stream=stream,
            )

            if not BUILD.exists():
                click.echo(
                    "❌ Normalization failed. Please review and fix build.md, then run 'vibe normalize' manually."
                )
                return
            click.echo("✅ Build specification normalized successfully.")

    from vibe_tools.ralph import RalphLoop

    agent = ctx.obj.get("agent", "cursor-agent")
    stream = ctx.obj.get("stream", False)

    loop = RalphLoop(
        name="Build",
        desired_file=BUILD,
        current_file=BUILD_CURRENT,
        agent=agent,
        stream=stream,
    )

    loop.instructions = [
        "Ensure the build system successfully builds all application parts.",
        "Verify that the built software can be started in the development environment.",
        "Check that all build dependencies are correctly configured.",
        "Ensure build artifacts are generated correctly.",
        "Test that the application starts successfully after building.",
        "Ensure the Makefile has comprehensive targets for: build, test, dev-start, dev-stop, dev-restart, lint, and coverage.",
        "If using Kubernetes, ensure Skaffold and Helm configurations are properly set up.",
        "Extract and document all services/components that need to run in development mode with their startup commands.",
    ]

    if loop.run():
        click.echo("✅ Build system reconciliation complete.")
        click.echo("\nNext Steps:")
        click.echo("[ ] Run the application (vibe run start)")
    else:
        click.echo("❌ Build system reconciliation failed.")


@cli.group()
@click.option(
    "--debug", "-d", is_flag=True, help="Enable debug output showing process detection details."
)
@click.pass_context
def run(ctx, debug):
    """Manage development environment: start, stop, restart, and view logs."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug


def _command_exists(cmd):
    """Check if a command exists in PATH."""
    import shutil
    return shutil.which(cmd) is not None


def _extract_services_from_build_config(build_config):
    """Extract services from build.yaml config."""
    services = build_config.get("services", [])
    if services:
        return services
    return []


def _extract_services_from_makefile():
    """Extract services by checking Makefile for dev-related targets."""
    makefile_path = pathlib.Path("Makefile")
    if not makefile_path.exists():
        return []

    services = []
    makefile_content = makefile_path.read_text()

    # Check for common dev start targets (in priority order)
    dev_targets = [
        ("dev-start", "make dev-start", "development"),
        ("dev", "make dev", "development"),
        ("run", "make run", "application"),
        ("start", "make start", "application"),
        ("up", "make up", "services"),
    ]

    found_main_target = False
    for target, cmd, service_name in dev_targets:
        if f"{target}:" in makefile_content or f".PHONY: {target}" in makefile_content:
            services.append(
                {
                    "name": service_name,
                    "start_command": cmd,
                    "stop_command": "make dev-stop" if "dev-stop:" in makefile_content else None,
                }
            )
            found_main_target = True
            break  # Use the first found

    # Check for Skaffold (only if skaffold is installed and config exists)
    if pathlib.Path("skaffold.yaml").exists() and _command_exists("skaffold"):
        services.append(
            {
                "name": "skaffold-dev",
                "start_command": "skaffold dev",
                "stop_command": "pkill -f skaffold",
            }
        )

    # Check for backend and frontend separately (only if main target not found)
    if not found_main_target:
        if "frontend-run:" in makefile_content or "frontend-dev:" in makefile_content:
            cmd = "make frontend-run" if "frontend-run:" in makefile_content else "make frontend-dev"
            services.append(
                {
                    "name": "frontend",
                    "start_command": cmd,
                }
            )
        if "run:" in makefile_content or "backend-run:" in makefile_content:
            cmd = "make backend-run" if "backend-run:" in makefile_content else "make run"
            services.append(
                {
                    "name": "backend",
                    "start_command": cmd,
                }
            )

    return services


def _extract_services_from_build_md():
    """Extract services from build.md by parsing startup commands."""
    if not BUILD_SPEC.exists():
        return []

    services = []
    build_md = BUILD_SPEC.read_text()

    # Look for startup commands section
    import re

    # Pattern to find commands like "make run", "make dev", "npm run dev", etc.
    startup_patterns = [
        r"`?make\s+(?:dev|run|start|up|dev-start)`?",
        r"`?npm\s+run\s+dev`?",
        r"`?python\s+manage\.py\s+runserver`?",
        r"`?uvicorn\s+.*`?",
        r"`?skaffold\s+dev`?",
    ]

    found_commands = set()
    for pattern in startup_patterns:
        matches = re.findall(pattern, build_md, re.IGNORECASE)
        for match in matches:
            cmd = match.strip("`").strip()
            if cmd and cmd not in found_commands:
                found_commands.add(cmd)
                service_name = cmd.split()[-1] if len(cmd.split()) > 1 else "service"
                services.append(
                    {
                        "name": service_name.replace("-", "_"),
                        "start_command": cmd,
                    }
                )

    return services


def _get_pid_file():
    """Get path to PID tracking file."""
    return VIBE_PROJECT_DIR / "run-pids.json"


def _load_pids():
    """Load tracked PIDs from file."""
    pid_file = _get_pid_file()
    if pid_file.exists():
        try:
            import json
            return json.loads(pid_file.read_text())
        except Exception:
            return {}
    return {}


def _save_pids(pids):
    """Save tracked PIDs to file."""
    pid_file = _get_pid_file()
    ensure_dir(pid_file.parent)
    import json
    pid_file.write_text(json.dumps(pids, indent=2))


def _get_services():
    """Get services from build.yaml, build.md, or Makefile."""
    services = []

    # Try build.yaml first
    build_file = BUILD_CURRENT if BUILD_CURRENT.exists() else BUILD
    if build_file.exists():
        try:
            import yaml

            build_config = yaml.safe_load(build_file.read_text())
            if build_config:
                services = _extract_services_from_build_config(build_config)
                if services:
                    return services
        except Exception:
            pass

    # Try Makefile
    services = _extract_services_from_makefile()
    if services:
        return services

    # Try build.md
    services = _extract_services_from_build_md()
    if services:
        return services

    # Fallback: try common commands
    makefile_path = pathlib.Path("Makefile")
    if makefile_path.exists():
        # Just try make dev or make run
        return [
            {
                "name": "development",
                "start_command": "make dev",
            }
        ]

    return []


@run.command()
@click.pass_context
def start(ctx):
    """Start all development services defined in build.yaml, build.md, or Makefile."""
    debug = ctx.obj.get("debug", False)
    services = _get_services()

    if debug:
        click.echo("🔍 DEBUG: Service detection:")
        click.echo(f"  Found {len(services)} service(s)")
        for i, service in enumerate(services, 1):
            click.echo(f"  {i}. {service.get('name', 'unknown')}: {service.get('start_command', 'N/A')}")
        click.echo("")

    if not services:
        click.echo("⚠️  Could not determine services to start.")
        click.echo("   Ensure build.yaml, build.md, or Makefile exists with dev startup commands.")
        click.echo("   Or run 'vibe build' to set up the build system.")
        return

    click.echo(f"🚀 Starting {len(services)} development service(s)...")

    started_count = 0
    for service in services:
        service_name = service.get("name", "unknown")
        start_cmd = service.get("start_command")
        if start_cmd:
            click.echo(f"  Starting {service_name}...")
            if isinstance(start_cmd, str):
                import shlex

                cmd_parts = shlex.split(start_cmd)
            else:
                cmd_parts = start_cmd

            # Check if command exists (for non-make commands)
            if cmd_parts and cmd_parts[0] != "make" and not _command_exists(cmd_parts[0]):
                click.echo(
                    f"  ⚠️  {service_name}: Command '{cmd_parts[0]}' not found. Skipping."
                )
                continue

            # Run in background
            try:
                # For make commands, we need to let them run and check for child processes
                if cmd_parts[0] == "make" and len(cmd_parts) > 1:
                    if debug:
                        click.echo(f"  🔍 DEBUG: Running make command: {' '.join(cmd_parts)}")
                    # Run make in background, but don't wait for it
                    process = subprocess.Popen(
                        cmd_parts,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=service.get("working_directory", "."),
                    )
                    if debug:
                        click.echo(f"  🔍 DEBUG: Make process started with PID: {process.pid}")
                    # Give it a moment to start child processes
                    import time
                    time.sleep(0.5)
                    # Try to find child processes
                    child_pids = []
                    try:
                        # Look for processes started by this make command
                        result = run_command(
                            ["pgrep", "-P", str(process.pid)], check=False
                        )
                        child_pids = result[0].strip().split() if result[0].strip() else []
                    except Exception:
                        pass
                    
                    if debug:
                        click.echo(f"  🔍 DEBUG: Child PIDs found: {child_pids}")
                        click.echo(f"  🔍 DEBUG: Make process still running: {process.poll() is None}")
                    # Also check if make is still running or if it spawned processes
                    if process.poll() is None or child_pids:
                        # Store the make PID and any child PIDs
                        pids = _load_pids()
                        pids[service_name] = {
                            "main_pid": process.pid,
                            "child_pids": child_pids,
                            "command": start_cmd,
                        }
                        _save_pids(pids)
                        if debug:
                            click.echo(f"  🔍 DEBUG: Saved PIDs to tracking file: {pids[service_name]}")
                        click.echo(f"  ✅ {service_name} started (PID: {process.pid})")
                        started_count += 1
                    else:
                            # Make completed quickly, check what it might have started
                            # Look for common dev server processes
                            target = cmd_parts[1] if len(cmd_parts) > 1 else ""
                            if debug:
                                click.echo(f"  🔍 DEBUG: Make completed quickly, checking Makefile for target: {target}")
                            # Check Makefile to see what the target runs
                            makefile_path = pathlib.Path("Makefile")
                            if makefile_path.exists():
                                makefile_content = makefile_path.read_text()
                                # Look for the target definition
                                import re
                                target_pattern = rf"^{target}:.*"
                                match = re.search(target_pattern, makefile_content, re.MULTILINE)
                                if match:
                                    # Try to extract what command it runs
                                    target_content = makefile_content[match.end():]
                                    if debug:
                                        click.echo(f"  🔍 DEBUG: Target content: {target_content[:200]}...")
                                    # Look for common commands in the target
                                    for proc_name in ["uvicorn", "python", "node", "npm", "yarn", "next", "vite"]:
                                        if proc_name in target_content.lower():
                                            # Store with process name to check later
                                            pids = _load_pids()
                                            pids[service_name] = {
                                                "main_pid": None,
                                                "process_name": proc_name,
                                                "command": start_cmd,
                                            }
                                            _save_pids(pids)
                                            if debug:
                                                click.echo(f"  🔍 DEBUG: Detected process name: {proc_name}")
                                                click.echo(f"  🔍 DEBUG: Saved to tracking file: {pids[service_name]}")
                                            click.echo(f"  ✅ {service_name} started (checking for {proc_name} processes)")
                                            started_count += 1
                                            break
                                    if debug and started_count == 0:
                                        click.echo(f"  🔍 DEBUG: No common process names found in target")
                                else:
                                    if debug:
                                        click.echo(f"  🔍 DEBUG: Target '{target}' not found in Makefile")
                            else:
                                if debug:
                                    click.echo(f"  🔍 DEBUG: Makefile not found")
                else:
                    # Direct command - track the PID
                    if debug:
                        click.echo(f"  🔍 DEBUG: Running direct command: {' '.join(cmd_parts)}")
                    process = subprocess.Popen(
                        cmd_parts,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=service.get("working_directory", "."),
                    )
                    pids = _load_pids()
                    pids[service_name] = {
                        "main_pid": process.pid,
                        "command": start_cmd,
                    }
                    _save_pids(pids)
                    if debug:
                        click.echo(f"  🔍 DEBUG: Saved PID {process.pid} to tracking file")
                    click.echo(f"  ✅ {service_name} started (PID: {process.pid})")
                    started_count += 1
            except FileNotFoundError as e:
                click.echo(
                    f"  ❌ {service_name} failed to start: Command not found. Is '{cmd_parts[0] if cmd_parts else 'unknown'}' installed?"
                )
            except Exception as e:
                click.echo(f"  ❌ {service_name} failed to start: {e}")
        else:
            click.echo(f"  ⚠️  {service_name}: No start_command defined")

    if started_count > 0:
        click.echo(f"✅ Started {started_count} service(s).")
    else:
        click.echo("⚠️  No services were started.")


@run.command()
@click.pass_context
def stop(ctx):
    """Stop all development services."""
    services = _get_services()
    tracked_pids = _load_pids()

    if not services:
        # Try make dev-stop as fallback
        makefile_path = pathlib.Path("Makefile")
        if makefile_path.exists() and "dev-stop:" in makefile_path.read_text():
            click.echo("🛑 Stopping development services...")
            run_command(["make", "dev-stop"], check=False)
            # Clear tracked PIDs
            _save_pids({})
            click.echo("✅ Development environment stopped.")
            return

        click.echo("⚠️  Could not determine services to stop.")
        return

    click.echo(f"🛑 Stopping development services...")

    # Stop services
    for service in services:
        service_name = service.get("name", "unknown")
        stop_cmd = service.get("stop_command")
        pid_info = tracked_pids.get(service_name, {})

        # First try to kill tracked PIDs
        if pid_info:
            main_pid = pid_info.get("main_pid")
            child_pids = pid_info.get("child_pids", [])
            process_name = pid_info.get("process_name")

            # Kill main PID and children
            if main_pid:
                try:
                    run_command(["kill", str(main_pid)], check=False)
                except Exception:
                    pass
            for child_pid in child_pids:
                try:
                    run_command(["kill", str(child_pid)], check=False)
                except Exception:
                    pass

            # Kill by process name if we have it
            if process_name:
                run_command(["pkill", "-f", process_name], check=False)

        if stop_cmd:
            if isinstance(stop_cmd, str):
                import shlex

                cmd = shlex.split(stop_cmd)
            else:
                cmd = stop_cmd
            run_command(cmd, check=False)
            click.echo(f"  ✅ {service_name} stopped")
        else:
            # Try to kill processes by name
            start_cmd = service.get("start_command", "")
            if start_cmd:
                # Extract command name (first word after 'make' or first word)
                cmd_parts = start_cmd.split()
                if len(cmd_parts) > 1 and cmd_parts[0] == "make":
                    # For make commands, try make dev-stop
                    makefile_path = pathlib.Path("Makefile")
                    if makefile_path.exists():
                        makefile_content = makefile_path.read_text()
                        if "dev-stop:" in makefile_content:
                            run_command(["make", "dev-stop"], check=False)
                            click.echo(f"  ✅ {service_name} stopped (via make dev-stop)")
                            continue
                # Try pkill for other commands
                proc_name = cmd_parts[0] if cmd_parts else ""
                if proc_name:
                    run_command(["pkill", "-f", proc_name], check=False)
                    click.echo(f"  ✅ {service_name} stopped (via pkill)")

    # Clear tracked PIDs
    _save_pids({})
    click.echo("✅ Development environment stopped.")


@run.command()
@click.pass_context
def restart(ctx):
    """Restart all development services."""
    ctx.invoke(stop)
    ctx.invoke(start)


@run.command()
@click.pass_context
def status(ctx):
    """Check status of development services."""
    debug = ctx.obj.get("debug", False)
    services = _get_services()

    if not services:
        click.echo("⚠️  Could not determine services to check.")
        click.echo("   Ensure build.yaml, build.md, or Makefile exists with dev startup commands.")
        return

    if debug:
        click.echo("🔍 DEBUG: Service detection:")
        click.echo(f"  Found {len(services)} service(s)")
        for i, service in enumerate(services, 1):
            click.echo(f"  {i}. {service.get('name', 'unknown')}: {service.get('start_command', 'N/A')}")
        click.echo("")

    click.echo("📊 Development environment status:")
    click.echo("-" * 60)

    running_count = 0
    stopped_count = 0

    # Load tracked PIDs
    tracked_pids = _load_pids()
    if debug:
        click.echo(f"🔍 DEBUG: Tracked PIDs from file: {tracked_pids}")
        click.echo("")

    for service in services:
        service_name = service.get("name", "unknown")
        start_cmd = service.get("start_command", "")

        # Try to determine if service is running
        is_running = False
        pid = None
        pid_info = tracked_pids.get(service_name, {})

        # First check tracked PIDs
        if pid_info:
            main_pid = pid_info.get("main_pid")
            child_pids = pid_info.get("child_pids", [])
            process_name = pid_info.get("process_name")

            # Check main PID if it exists
            if main_pid:
                if debug:
                    click.echo(f"  🔍 DEBUG: Checking main PID {main_pid}")
                # Check if process is still running (kill -0 just checks, doesn't kill)
                _, code = run_command(["kill", "-0", str(main_pid)], check=False)
                if code == 0:
                    is_running = True
                    pid = str(main_pid)
                    if debug:
                        click.echo(f"  🔍 DEBUG: Main PID {main_pid} is running")
                else:
                    if debug:
                        click.echo(f"  🔍 DEBUG: Main PID {main_pid} is not running, checking child PIDs")
                    # Check child PIDs
                    for child_pid in child_pids:
                        _, code = run_command(["kill", "-0", str(child_pid)], check=False)
                        if code == 0:
                            is_running = True
                            pid = str(child_pid)
                            if debug:
                                click.echo(f"  🔍 DEBUG: Child PID {child_pid} is running")
                            break

            # If we have a process name, check for it
            if not is_running and process_name:
                if debug:
                    click.echo(f"  🔍 DEBUG: Checking for process name: {process_name}")
                try:
                    result = run_command(
                        ["pgrep", "-f", process_name], check=False
                    )
                    if result[0].strip():
                        is_running = True
                        pids = result[0].strip().split()
                        pid = pids[0] if pids else None
                        if debug:
                            click.echo(f"  🔍 DEBUG: Found process(es): {pids}")
                except Exception as e:
                    if debug:
                        click.echo(f"  🔍 DEBUG: Error checking process name: {e}")

        # Fallback: try to detect by command
        if not is_running and start_cmd:
            if debug:
                click.echo(f"  🔍 DEBUG: Fallback detection for command: {start_cmd}")
            import shlex

            cmd_parts = shlex.split(start_cmd) if isinstance(start_cmd, str) else start_cmd

            if cmd_parts:
                # For make commands, check what the make target actually runs
                if cmd_parts[0] == "make" and len(cmd_parts) > 1:
                    target = cmd_parts[1]
                    if debug:
                        click.echo(f"  🔍 DEBUG: Parsing Makefile for target: {target}")
                    # Check Makefile to see what processes the target starts
                    makefile_path = pathlib.Path("Makefile")
                    if makefile_path.exists():
                        makefile_content = makefile_path.read_text()
                        import re
                        # Find the target and what it runs
                        target_pattern = rf"^{target}:.*?^[a-zA-Z]"
                        match = re.search(target_pattern, makefile_content, re.MULTILINE | re.DOTALL)
                        if match:
                            target_content = match.group(0)
                            if debug:
                                click.echo(f"  🔍 DEBUG: Target content: {target_content[:200]}...")
                            # Look for common dev server processes
                            for proc_name in ["uvicorn", "python.*manage\.py", "node", "npm.*dev", "yarn.*dev", "next", "vite"]:
                                if debug:
                                    click.echo(f"  🔍 DEBUG: Checking for process: {proc_name}")
                                try:
                                    result = run_command(
                                        ["pgrep", "-f", proc_name], check=False
                                    )
                                    if result[0].strip():
                                        is_running = True
                                        pids = result[0].strip().split()
                                        pid = pids[0] if pids else None
                                        if debug:
                                            click.echo(f"  🔍 DEBUG: Found process(es): {pids}")
                                        break
                                except Exception as e:
                                    if debug:
                                        click.echo(f"  🔍 DEBUG: Error checking {proc_name}: {e}")
                else:
                    # For direct commands, check if process is running
                    proc_name = cmd_parts[0]
                    if debug:
                        click.echo(f"  🔍 DEBUG: Checking for direct command process: {proc_name}")
                    try:
                        result = run_command(
                            ["pgrep", "-f", proc_name], check=False
                        )
                        if result[0].strip():
                            is_running = True
                            pids = result[0].strip().split()
                            pid = pids[0] if pids else None
                            if debug:
                                click.echo(f"  🔍 DEBUG: Found process(es): {pids}")
                    except Exception as e:
                        if debug:
                            click.echo(f"  🔍 DEBUG: Error checking process: {e}")

        status_icon = "🟢" if is_running else "🔴"
        status_text = f"Running (PID: {pid})" if is_running else "Stopped"
        click.echo(f"{status_icon} {service_name:<20} {status_text}")

        if is_running:
            running_count += 1
        else:
            stopped_count += 1

    click.echo("-" * 60)
    click.echo(f"Total: {len(services)} service(s) - {running_count} running, {stopped_count} stopped")

    if stopped_count > 0:
        click.echo("\n💡 Run 'vibe start' or 'vibe run start' to start stopped services.")


@run.command()
@click.pass_context
def logs(ctx):
    """Show logs for development services."""
    services = _get_services()

    if not services:
        click.echo("⚠️  Could not determine services to show logs for.")
        return

    click.echo("📋 Development service logs:")
    click.echo("-" * 60)

    for service in services:
        service_name = service.get("name", "unknown")
        log_file = service.get("log_file")
        if log_file:
            log_path = pathlib.Path(log_file)
            if log_path.exists():
                click.echo(f"\n{service_name} ({log_file}):")
                click.echo(log_path.read_text()[-2000:])  # Last 2000 chars
            else:
                click.echo(f"\n{service_name}: Log file not found: {log_file}")
        else:
            # Try to show logs from common locations
            common_logs = [
                pathlib.Path("logs") / f"{service_name}.log",
                pathlib.Path(f"{service_name}.log"),
                pathlib.Path(".logs") / f"{service_name}.log",
            ]
            found = False
            for log_path in common_logs:
                if log_path.exists():
                    click.echo(f"\n{service_name} ({log_path}):")
                    click.echo(log_path.read_text()[-2000:])
                    found = True
                    break
            if not found:
                click.echo(f"\n{service_name}: No log file found (check logs/ directory)")


@cli.command()
@click.pass_context
def start(ctx):
    """Shortcut for 'vibe run start' - Start all development services."""
    ctx.invoke(run.get_command(ctx, "start"))


@cli.command()
@click.pass_context
def stop(ctx):
    """Shortcut for 'vibe run stop' - Stop all development services."""
    ctx.invoke(run.get_command(ctx, "stop"))


@cli.command(name="run-status")
@click.pass_context
def run_status(ctx):
    """Shortcut for 'vibe run status' - Check status of development services."""
    ctx.invoke(run.get_command(ctx, "status"))


@cli.command()
@click.pass_context
def infra(ctx):
    """Phase 6: Infrastructure reconciliation for production and live-staging environments.
    
    Sets up infrastructure for production and live-staging systems (Kubernetes, cloud platforms, etc.).
    This step is optional depending on the distribution needs of the project - not all projects
    require a production environment.
    
    Note: For development environment management, use 'vibe build' and 'vibe run' instead.
    """
    state = load_project_state()
    missing = check_dependencies("infra", state)
    if missing:
        click.echo(
            f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first."
        )
        return

    # Handle missing infrastructure files
    if not INFRA.exists():
        if INFRA_SPEC.exists():
            # infrastructure.md exists but not normalized - auto-normalize it
            click.echo(f"📝 {INFRA_SPEC} found but not normalized. Normalizing...")
            from vibe_tools.normalize import normalize_prd

            normalize_prd(
                agent=ctx.obj.get("agent", "cursor-agent"),
                input_file=str(INFRA_SPEC),
                auto_overwrite=True,
                caffeinate=ctx.obj.get("caffeinate", False),
                stream=ctx.obj.get("stream", False),
            )
            if not INFRA.exists():
                click.echo(
                    "❌ Normalization failed. Please review and fix infrastructure.md, then run 'vibe normalize' manually."
                )
                return
            click.echo("✅ Infrastructure normalized successfully.")
        else:
            # Neither exists - generate from PRDs
            click.echo(
                "📋 Infrastructure specification not found. Generating from PRDs..."
            )
            from vibe_tools.utils import collect_all_prd_info

            prd_info = collect_all_prd_info()
            if not prd_info:
                click.echo(
                    "❌ No PRDs found. Please create PRDs first using 'vibe pm' or 'vibe architect'."
                )
                return

            # Generate infrastructure.md from PRDs
            agent = ctx.obj.get("agent", "cursor-agent")
            stream = ctx.obj.get("stream", False)

            # Collect PRD content
            prd_content = []
            for prd in prd_info:
                content_parts = []
                if prd.get("has_md") and prd["md_path"]:
                    content_parts.append(
                        f"## {prd['name']} (from {prd['md_path'].name})\n\n{prd['md_path'].read_text()}\n"
                    )
                if prd.get("has_yaml") and prd["yaml_path"]:
                    content_parts.append(
                        f"## {prd['name']} (from {prd['yaml_path'].name})\n\n```yaml\n{prd['yaml_path'].read_text()}\n```\n"
                    )
                if content_parts:
                    prd_content.append("\n".join(content_parts))

            if not prd_content:
                click.echo("❌ No PRD content found. Please ensure PRDs have content.")
                return

            # Generate infrastructure.md using agent
            prompt = f"""You are generating an infrastructure specification based on the following PRDs.

Analyze all the PRDs and create a comprehensive infrastructure.md file that specifies:
- Databases and data storage needs
- Caching requirements (Redis, etc.)
- Message queues if needed
- Object storage (S3-compatible)
- External service integrations
- Environment configuration
- Local development setup requirements

IMPORTANT: The infrastructure must be compatible with vibe-staging, which supports these services:
- postgres (PostgreSQL database)
- redis (Redis cache)
- rabbitmq (RabbitMQ message queue)
- elasticsearch (Elasticsearch search)
- s3-linode or s3-aws (MinIO S3-compatible storage)
- mailhog (Email testing)
- imgproxy (Image processing)

Services are configured via 'vibe-setup <service>' and stored in .vibe_config.json. The staging environment uses these service configurations to start Docker containers.

Focus on what infrastructure components are needed to support all the features described in the PRDs, and ensure they can be run locally via Docker for staging.

PRDs:
{chr(10).join(prd_content)}

Generate a complete infrastructure.md file following this structure:

# Infrastructure Specification (Desired)

## 1. Overview
[High-level overview of infrastructure needs, emphasizing local development and staging compatibility]

## 2. Primary Services
[Detailed service requirements for each service needed. For each service, specify:
- What it's used for
- Local development setup (Docker-based)
- Configuration requirements
- How it integrates with vibe-staging]

## 3. External Integrations
[External APIs and services that are not managed locally]

## 4. Environment Management
[Configuration and secrets management, including .env files and vibe-setup usage]

## 5. Deployment & Local Orchestration
[Local development setup requirements, Docker containers, and how vibe-staging orchestrates services]

Output ONLY the markdown content for infrastructure.md, starting with the title and ending with the last section. Do not include code fences or explanations.
"""

            cmd = get_agent_command(agent, prompt)
            output, code = run_agent(cmd, stream=stream)

            if code != 0 or not output.strip():
                click.echo(
                    "❌ Failed to generate infrastructure.md. Please create it manually using 'vibe architect'."
                )
                return

            # Clean output (remove code fences if present)
            clean_output = output.strip()
            if clean_output.startswith("```"):
                lines = clean_output.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_output = "\n".join(lines).strip()

            # Write infrastructure.md
            ensure_dir(INFRA_SPEC.parent)
            INFRA_SPEC.write_text(clean_output)
            click.echo(f"✅ Generated {INFRA_SPEC}")
            click.echo(
                "📝 Please review the generated infrastructure.md, then it will be normalized automatically."
            )

            # Auto-normalize
            click.echo("🔄 Normalizing infrastructure.md...")
            from vibe_tools.normalize import normalize_prd

            normalize_prd(
                agent=agent,
                input_file=str(INFRA_SPEC),
                auto_overwrite=True,
                caffeinate=ctx.obj.get("caffeinate", False),
                stream=stream,
            )

            if not INFRA.exists():
                click.echo(
                    "❌ Normalization failed. Please review and fix infrastructure.md, then run 'vibe normalize' manually."
                )
                return
            click.echo("✅ Infrastructure normalized successfully.")

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

    # Custom instruction for infra verification and generation
    loop.instructions = [
        "Generate Kubernetes manifests for local staging deployment.",
        "Create infrastructure deployment configurations for target platforms (Linode, AWS, Hetzner, DigitalOcean, bare-metal).",
        "Set up Docker build system with Dockerfiles and build scripts.",
        "Ensure all build commands are configured in the Makefile.",
        "Specifically verify that all configured services (databases, queues, etc.) are reachable from the application environment.",
        "Test connectivity using appropriate tools (e.g., pg_isready, redis-cli, curl).",
        "Set up or update environment variables as needed.",
    ]

    if loop.run():
        state["phases"]["infra"]["status"] = "completed"
        save_project_state(state)
        click.echo("✅ Infrastructure reconciliation complete.")

        # Generate infrastructure deployment configs
        click.echo("\n📦 Generating infrastructure deployment configurations...")
        from vibe_tools.infrastructure import generate_all_infrastructure

        try:
            infra_results = generate_all_infrastructure(
                platforms=["linode", "aws", "hetzner", "digitalocean", "bare-metal"],
                build_system=True,
            )

            click.echo("✅ Generated infrastructure configs:")
            for platform, config in infra_results.get("platforms", {}).items():
                if "error" not in config:
                    click.echo(
                        f"  ✅ {platform}: {config.get('terraform_file', 'config generated')}"
                    )
                else:
                    click.echo(f"  ⚠️  {platform}: {config.get('error')}")

            if infra_results.get("build_system"):
                build_cfg = infra_results["build_system"]
                if "error" not in build_cfg:
                    click.echo(
                        f"  ✅ Build system: {build_cfg.get('dockerfile', 'configured')}"
                    )
        except Exception as e:
            click.echo(f"  ⚠️  Infrastructure generation warning: {e}")

        # Generate k8s manifests for local staging
        click.echo("\n☸️  Generating Kubernetes manifests for local staging...")
        from vibe_tools.staging import get_required_services, generate_k8s_manifests
        from vibe_tools.utils import load_config

        try:
            config = load_config()
            services = get_required_services()
            app_services = config.get("staging", {}).get("app_services", [])

            if services or app_services:
                from vibe_tools.staging import K8S_MANIFESTS_DIR

                K8S_MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

                manifests = generate_k8s_manifests(
                    services, app_services, "staging", isolated=False
                )

                for i, manifest in enumerate(manifests):
                    kind = manifest.get("kind", "unknown").lower()
                    name = manifest.get("metadata", {}).get("name", f"resource{i}")
                    filename = f"{kind}-{name}.yaml"
                    filepath = K8S_MANIFESTS_DIR / filename
                    filepath.write_text(yaml.dump(manifest, default_flow_style=False))

                click.echo(
                    f"  ✅ Generated {len(manifests)} Kubernetes manifests in {K8S_MANIFESTS_DIR}"
                )
        except Exception as e:
            click.echo(f"  ⚠️  K8s manifest generation warning: {e}")

        # Setup and run build system
        click.echo("\n🔨 Setting up build system and building...")
        from vibe_tools.infrastructure import BUILD_DIR, DEPLOYMENT_DIR

        try:
            # Check if build script exists
            build_script = BUILD_DIR / "build.sh"
            if build_script.exists():
                click.echo("  Running build script...")
                stdout, code = run_command(
                    ["bash", str(build_script)],
                    check=False,
                    cwd=Path.cwd(),
                )
                if code == 0:
                    click.echo("  ✅ Build complete")
                else:
                    click.echo(f"  ⚠️  Build script returned code {code}")
            else:
                # Fallback: try docker build directly
                dockerfile = DEPLOYMENT_DIR / "Dockerfile"
                if dockerfile.exists():
                    click.echo("  Building Docker image...")
                    stdout, code = run_command(
                        [
                            "docker",
                            "build",
                            "-t",
                            "vibe-app:latest",
                            "-f",
                            str(dockerfile),
                            ".",
                        ],
                        check=False,
                    )
                    if code == 0:
                        click.echo("  ✅ Docker image built")
                    else:
                        click.echo(f"  ⚠️  Docker build failed: {stdout[:200]}")
                else:
                    click.echo("  ⚠️  No build script or Dockerfile found")
        except Exception as e:
            click.echo(f"  ⚠️  Build system warning: {e}")

        # Setup staging servers
        click.echo("\n🔧 Setting up staging servers...")
        from vibe_tools.staging import get_required_services
        from vibe_tools.servers import get_server_configs, get_container_status

        services = get_required_services()
        server_configs = get_server_configs()

        # Ensure required services are running
        for service_key, service_config in services.items():
            server_key = None
            for sk in [
                "postgres",
                "redis",
                "rabbitmq",
                "elasticsearch",
                "minio-linode",
                "minio-aws",
                "mailhog",
                "imgproxy",
            ]:
                if (
                    service_key == sk
                    or (service_key == "s3-linode" and sk == "minio-linode")
                    or (service_key == "s3-aws" and sk == "minio-aws")
                ):
                    server_key = sk
                    break

            if server_key and server_key in server_configs:
                container_name = server_configs[server_key].get("container_name")
                if container_name:
                    status = get_container_status(container_name)
                    if status != "running":
                        click.echo(f"  Starting {service_key}...")
                        stdout, code = run_command(
                            ["docker", "start", container_name], check=False
                        )
                        if code == 0:
                            click.echo(f"  ✅ {service_key} started")
                        else:
                            click.echo(
                                f"  ⚠️  {service_key} not running (may need: vibe-servers install {server_key})"
                            )

        # Start staging environment
        click.echo("\n🚀 Starting staging environment...")
        from vibe_tools.staging import staging_cli

        try:
            ctx_staging = click.Context(staging_cli)
            ctx_staging.invoke(
                staging_cli.get_command(ctx_staging, "up"), isolated=False
            )
        except Exception as e:
            click.echo(f"  ⚠️  Staging setup warning: {e}")

        click.echo("\n✅ Infrastructure setup complete!")
        click.echo("\nNext Steps:")
        click.echo("[ ] Run Tests & Reconciliation (vibe testing)")
        click.echo("[ ] Review deployment configs in deployment/ directory")
        click.echo("[ ] Setup demo data (vibe demo-data setup)")
    else:
        click.echo("❌ Infrastructure reconciliation failed.")


@cli.command()
@click.pass_context
def cicd(ctx):
    """Phase 8: CI/CD reconciliation. Ensures deployment pipelines are ready."""
    state = load_project_state()
    missing = check_dependencies("cicd", state)
    if missing:
        click.echo(
            f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first."
        )
        return

    if not CICD.exists():
        if CICD_SPEC.exists():
            click.echo(f"❌ {CICD} not found, but {CICD_SPEC} exists.")
            click.echo("   Run 'vibe normalize' to generate the required YAML file.")
        else:
            click.echo(
                f"❌ {CICD} not found. Please create it manually or via 'vibe architect' + 'vibe normalize'."
            )
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
        "Ensure secrets and environment variables required for deployment are correctly handled.",
    ]

    if loop.run():
        state["phases"]["cicd"]["status"] = "completed"
        save_project_state(state)
        click.echo("✅ CI/CD reconciliation complete.")
        click.echo("\nNext Steps:")
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


@cli.command()
@click.pass_context
def deploy(ctx):
    """Phase 9: Deployment."""
    state = load_project_state()
    missing = check_dependencies("deploy", state)
    if missing:
        click.echo(
            f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first."
        )
        return

    # TODO: Implement deployment logic
    click.echo("🚀 Triggering deployment...")
    state["phases"]["deploy"]["status"] = "completed"
    save_project_state(state)
    click.echo("\n✨ Project fully deployed! All lifecycle phases completed.")


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
    click.echo(f"Rerunning PRD: {project_name}")

    messages = reset_prd_state(project_name)
    for msg in messages:
        click.echo(f"✅ {msg}")

    click.echo(f"\nReady to rerun: {project_name} state has been reset.")


@cli.command()
def implemented():
    """List implemented PRDs (batched) and optionally reset them."""
    state = load_project_state()
    completed = state.get("completed_prds", [])

    if not completed:
        click.echo("No implemented PRDs found.")
        return

    # Sort reverse (last implemented first)
    completed = list(reversed(completed))

    batch_size = 10
    current_idx = 0

    while current_idx < len(completed):
        batch = completed[current_idx : current_idx + batch_size]
        click.echo(
            click.style(
                f"\n--- Implemented PRDs (Batch {current_idx // batch_size + 1}) ---",
                fg="green",
                bold=True,
            )
        )
        for i, prd_name in enumerate(batch, 1):
            click.echo(f"  {i}. {prd_name}")

        click.echo("-" * 40)
        options = ["q"]
        prompt_parts = ["[q]uit"]

        if current_idx + batch_size < len(completed):
            options.append("n")
            prompt_parts.append("[n]ext batch")

        # Add number options
        num_options = [str(i) for i in range(1, len(batch) + 1)]
        options.extend(num_options)
        prompt_parts.append("[1-10] to reset")

        prompt_text = f"Select an option ({', '.join(prompt_parts)})"
        choice = click.prompt(prompt_text, type=click.Choice(options), default="q")

        if choice == "q":
            break
        elif choice == "n":
            current_idx += batch_size
        elif choice in num_options:
            selected_prd = batch[int(choice) - 1]
            if click.confirm(
                f"Are you sure you want to reset '{selected_prd}'?", default=False
            ):
                messages = reset_prd_state(selected_prd)
                for msg in messages:
                    click.echo(f"✅ {msg}")
                # Update completed list for display
                completed.remove(selected_prd)
                if not completed:
                    click.echo("No more implemented PRDs.")
                    break
            else:
                click.echo("Reset cancelled.")

    click.echo("Done.")


@cli.group(name="branch")
@click.pass_context
def branch_group(ctx):
    """Manage feature branches and their lineage."""
    pass


@branch_group.command(name="base")
@click.argument("branch_name", required=False)
@click.argument("new_base", required=False)
@click.pass_context
def branch_base(ctx, branch_name, new_base):
    """Get or set the base branch for a feature branch."""
    from vibe_tools.branches import set_branch_base
    from vibe_tools.utils import load_project_state, run_command, get_main_branch

    if not branch_name:
        # Show current branch and its base
        branch_name, _ = run_command(["git", "branch", "--show-current"], check=False)
        branch_name = branch_name.strip()

    state = load_project_state()
    lineage = state.get("branch_lineage", {})

    if new_base:
        set_branch_base(branch_name, new_base)
    else:
        current_base = lineage.get(branch_name, get_main_branch())
        click.echo(
            f"Branch {click.style(branch_name, fg='cyan')} is based on {click.style(current_base, fg='blue')}"
        )


@branch_group.command(name="merge")
@click.argument("src")
@click.argument("dst")
@click.pass_context
def branch_merge(ctx, src, dst):
    """Merge src into dst and update lineage."""
    from vibe_tools.branches import merge_branches

    merge_branches(src, dst)


@branch_group.command(name="automerge")
@click.argument("branch_name", required=False)
@click.pass_context
def branch_automerge(ctx, branch_name):
    """Get or set the automerge branch."""
    config = load_config()
    if "ralph" not in config:
        config["ralph"] = {}

    if branch_name:
        main_branch = get_main_branch()
        if branch_name == main_branch:
            click.echo(
                click.style(
                    f"❌ Automerge branch cannot be the main branch ({main_branch}).",
                    fg="red",
                )
            )
            return

        config["ralph"]["automerge_branch"] = branch_name
        save_config(config)
        click.echo(f"✅ Automerge branch set to: {click.style(branch_name, fg='cyan')}")

        # Verify if branch exists, if not, inform user it will be created on first use
        _, code = run_command(
            ["git", "rev-parse", "--verify", branch_name], check=False
        )
        if code != 0:
            click.echo(
                click.style(
                    f"ℹ️ Branch '{branch_name}' does not exist yet. It will be created when needed.",
                    fg="yellow",
                )
            )
    else:
        current_automerge = get_automerge_branch(config)
        click.echo(
            f"Current automerge branch: {click.style(current_automerge, fg='cyan')}"
        )


@branch_group.command(name="investigate")
@click.pass_context
def branch_investigate(ctx):
    """Reconstruct branch lineage from git history."""
    from vibe_tools.branches import investigate_git_lineage

    investigate_git_lineage()


@cli.command()
@click.pass_context
def branches(ctx):
    """List all local branches and their dependencies."""
    from vibe_tools.branches import display_branches_table

    display_branches_table()


@cli.command(name="branch-resolve")
@click.pass_context
def branch_resolve(ctx):
    """Use the agent to resolve git history/conflicts across the branch stack."""
    from vibe_tools.utils import get_agent_command, get_prompt, run_agent, run_command

    agent = ctx.obj.get("agent", "cursor-agent")
    stream = ctx.obj.get("stream", False)
    caffeinate = ctx.obj.get("caffeinate", False)

    click.echo("🔍 Analyzing git history and branch lineage...")

    git_status, _ = run_command(["git", "status"], check=False)
    git_log, _ = run_command(
        ["git", "log", "--oneline", "--graph", "--all", "-n", "20"], check=False
    )
    git_branches, _ = run_command(["git", "branch", "-a"], check=False)

    state = load_project_state()
    lineage = json.dumps(state.get("branch_lineage", {}), indent=2)

    try:
        prompt_template = get_prompt("git_resolve_prompt.txt")
    except FileNotFoundError:
        click.echo("❌ Prompt template 'git_resolve_prompt.txt' not found.")
        return

    prompt = prompt_template.format(
        git_status=git_status,
        git_log=git_log,
        git_branches=git_branches,
        lineage=lineage,
    )

    click.echo(f"🤖 Calling {agent} to resolve git state...")
    cmd = get_agent_command(agent, prompt)
    output, code = run_agent(cmd, caffeinate=caffeinate, stream=stream)

    if code == 0:
        click.echo("✅ Git resolution attempt completed.")
    else:
        click.echo(f"❌ Git resolution failed (exit code {code}).")


@cli.command()
def ps():
    """List active agent processes."""
    processes = get_agent_processes()
    if not processes:
        click.echo("No active agent processes found.")
        return

    click.echo(f"{'PID':<10} {'TARGET':<20} {'COMMAND'}")
    click.echo("-" * 60)
    for p in processes:
        click.echo(f"{p['pid']:<10} {p['target']:<20} {p['command']}")


@cli.command()
@click.option("--yes", "-y", is_flag=True, help="Automatically confirm kill.")
def kill(yes):
    """Kill all active agent processes."""
    processes = get_agent_processes()
    if not processes:
        click.echo("No active agent processes found.")
        return

    if not yes:
        click.echo("Active agent processes:")
        for p in processes:
            click.echo(f"  - {p['pid']}: {p['command']}")

        if not click.confirm(
            "\nAre you sure you want to kill all these processes?", default=False
        ):
            click.echo("Aborted.")
            return

    killed = cleanup_stale_processes()
    if killed:
        click.echo(f"✅ Killed processes for: {', '.join(killed)}")
    else:
        click.echo("No processes were killed.")


@cli.command()
@click.option(
    "--api", is_flag=True, help="Fetch data from Cursor API instead of local files."
)
@click.option("--billing-groups", is_flag=True, help="Show billing groups report.")
@click.option(
    "--days", type=int, default=7, help="Number of days to fetch from API (default: 7)."
)
@click.option("--start-date", help="Start date for API query (YYYY-MM-DD).")
@click.option("--end-date", help="End date for API query (YYYY-MM-DD).")
@click.pass_context
def stats(ctx, api, billing_groups, days, start_date, end_date):
    """Generate statistics report from usage files or Cursor API."""
    from vibe_tools.stats import (
        generate_report,
        generate_billing_groups_report,
        list_usage_files,
        fetch_daily_usage_data,
        fetch_spending_data,
        fetch_usage_events,
        list_billing_groups,
        get_billing_group,
    )
    from vibe_tools.utils import get_cursor_api_key

    reports_dir = pathlib.Path("reports")

    if billing_groups or api:
        api_key = get_cursor_api_key()
        if not api_key:
            click.echo(
                "❌ CURSOR_API_KEY not found. Set it in .env file or environment."
            )
            click.echo(
                "   You can get your API key from: https://cursor.com/settings/api-keys"
            )
            return

        if billing_groups:
            try:
                click.echo("📊 Fetching billing groups...")
                groups_data = list_billing_groups(api_key)
                markdown = generate_billing_groups_report(groups_data)

                reports_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                report_path = reports_dir / f"report_billing_groups_{timestamp}.md"
                report_path.write_text(markdown, encoding="utf-8")
                click.echo(f"✅ Billing groups report generated: {report_path}")
            except Exception as e:
                click.echo(f"❌ Error fetching billing groups: {e}")
                import traceback

                traceback.print_exc()
            return

        # API data fetching
        try:
            if start_date and end_date:
                start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
            else:
                end = datetime.datetime.now()
                start = end - datetime.timedelta(days=days)

            click.echo(
                f"📊 Fetching usage events from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}..."
            )

            all_events = []
            page = 1
            while True:
                api_data = fetch_usage_events(
                    api_key, start, end, page=page, page_size=100
                )
                events = api_data.get("usageEvents", [])
                if not events:
                    break
                all_events.extend(events)

                pagination = api_data.get("pagination", {})
                if not pagination.get("hasNextPage", False):
                    break
                page += 1

            if not all_events:
                click.echo("No usage events found for the specified period.")
                return

            api_data["usageEvents"] = all_events
            report_path = generate_report(
                None, reports_dir, api_data, source="Cursor API"
            )
            click.echo(f"✅ Report generated: {report_path}")
        except Exception as e:
            click.echo(f"❌ Error fetching API data: {e}")
            import traceback

            traceback.print_exc()
        return

    # Local file processing
    stats_dir = pathlib.Path("stats")

    if not stats_dir.exists():
        click.echo(f"❌ Stats directory '{stats_dir}' not found.")
        return

    files = list_usage_files(stats_dir)
    if not files:
        click.echo(f"No CSV files found in '{stats_dir}'.")
        return

    click.echo("Available usage files (latest first):")
    for idx, file_path in enumerate(files, start=1):
        import re

        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", file_path.name)
        if date_match:
            date_str = date_match.group(1)
        else:
            date_str = datetime.datetime.fromtimestamp(
                file_path.stat().st_mtime
            ).strftime("%Y-%m-%d")
        click.echo(f"  {idx}. {file_path.name} ({date_str})")

    while True:
        try:
            selection = click.prompt(
                "\nSelect a file to analyze",
                type=int,
                default=1,
            )
            if 1 <= selection <= len(files):
                selected_file = files[selection - 1]
                break
            click.echo("Invalid selection. Please choose a number from the list.")
        except (ValueError, KeyboardInterrupt):
            click.echo("Aborted.")
            return

    click.echo(f"\n📊 Analyzing {selected_file.name}...")

    try:
        report_path = generate_report(selected_file, reports_dir)
        click.echo(f"✅ Report generated: {report_path}")
    except Exception as e:
        click.echo(f"❌ Error generating report: {e}")
        import traceback

        traceback.print_exc()


@cli.group(name="billing-groups")
@click.pass_context
def billing_groups_group(ctx):
    """Manage billing groups for tracking costs per project."""
    pass


@billing_groups_group.command(name="list")
@click.option("--billing-cycle", help="Billing cycle date (YYYY-MM-DD).")
@click.pass_context
def billing_groups_list(ctx, billing_cycle):
    """List all billing groups."""
    from vibe_tools.stats import list_billing_groups, generate_billing_groups_report
    from vibe_tools.utils import get_cursor_api_key

    api_key = get_cursor_api_key()
    if not api_key:
        click.echo("❌ CURSOR_API_KEY not found. Set it in .env file or environment.")
        return

    try:
        groups_data = list_billing_groups(api_key, billing_cycle)
        reports_dir = pathlib.Path("reports")
        reports_dir.mkdir(parents=True, exist_ok=True)

        markdown = generate_billing_groups_report(groups_data)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = reports_dir / f"report_billing_groups_{timestamp}.md"
        report_path.write_text(markdown, encoding="utf-8")
        click.echo(f"✅ Billing groups report generated: {report_path}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


@billing_groups_group.command(name="create")
@click.argument("name")
@click.pass_context
def billing_groups_create(ctx, name):
    """Create a new billing group."""
    from vibe_tools.stats import create_billing_group
    from vibe_tools.utils import get_cursor_api_key

    api_key = get_cursor_api_key()
    if not api_key:
        click.echo("❌ CURSOR_API_KEY not found.")
        return

    try:
        result = create_billing_group(api_key, name)
        group = result.get("group", {})
        click.echo(
            f"✅ Created billing group: {group.get('name')} (ID: {group.get('id')})"
        )
    except Exception as e:
        click.echo(f"❌ Error: {e}")


@billing_groups_group.command(name="get")
@click.argument("group_id")
@click.option("--billing-cycle", help="Billing cycle date (YYYY-MM-DD).")
@click.pass_context
def billing_groups_get(ctx, group_id, billing_cycle):
    """Get details of a specific billing group."""
    from vibe_tools.stats import get_billing_group, generate_billing_groups_report
    from vibe_tools.utils import get_cursor_api_key

    api_key = get_cursor_api_key()
    if not api_key:
        click.echo("❌ CURSOR_API_KEY not found.")
        return

    try:
        result = get_billing_group(api_key, group_id, billing_cycle)
        groups_data = {"groups": [], "billingCycle": result.get("billingCycle", {})}
        if "group" in result:
            groups_data["groups"] = [result["group"]]

        reports_dir = pathlib.Path("reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        markdown = generate_billing_groups_report(groups_data)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = reports_dir / f"report_billing_group_{group_id}_{timestamp}.md"
        report_path.write_text(markdown, encoding="utf-8")
        click.echo(f"✅ Report generated: {report_path}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")


@billing_groups_group.command(name="add-members")
@click.argument("group_id")
@click.argument("user_ids", nargs=-1, required=True)
@click.pass_context
def billing_groups_add_members(ctx, group_id, user_ids):
    """Add members to a billing group."""
    from vibe_tools.stats import add_members_to_group
    from vibe_tools.utils import get_cursor_api_key

    api_key = get_cursor_api_key()
    if not api_key:
        click.echo("❌ CURSOR_API_KEY not found.")
        return

    try:
        result = add_members_to_group(api_key, group_id, list(user_ids))
        group = result.get("group", {})
        click.echo(f"✅ Added {len(user_ids)} member(s) to group: {group.get('name')}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")


@billing_groups_group.command(name="remove-members")
@click.argument("group_id")
@click.argument("user_ids", nargs=-1, required=True)
@click.pass_context
def billing_groups_remove_members(ctx, group_id, user_ids):
    """Remove members from a billing group."""
    from vibe_tools.stats import remove_members_from_group
    from vibe_tools.utils import get_cursor_api_key

    api_key = get_cursor_api_key()
    if not api_key:
        click.echo("❌ CURSOR_API_KEY not found.")
        return

    try:
        result = remove_members_from_group(api_key, group_id, list(user_ids))
        group = result.get("group", {})
        click.echo(
            f"✅ Removed {len(user_ids)} member(s) from group: {group.get('name')}"
        )
    except Exception as e:
        click.echo(f"❌ Error: {e}")


@click.group()
def demo_data_cli():
    """Manage demo data for staging environment."""
    pass


@demo_data_cli.command()
@click.pass_context
def design(ctx):
    """Design demo data PRD in specs/demodata.md using PM system."""
    from vibe_tools.pm import InteractivePM

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
    from vibe_tools.staging import (
        get_required_services,
        check_service_health,
        detect_environment,
    )

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
        from vibe_tools.staging import staging_cli

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


if __name__ == "__main__":
    cli()
