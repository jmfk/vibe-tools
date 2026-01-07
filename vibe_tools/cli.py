import atexit
import datetime
import json
import logging
import pathlib
from typing import List

import click


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
            "testing",
            "infra",
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
@click.argument("input_file", required=False)
@click.option(
    "--yes", "-y", is_flag=True, help="Automatically overwrite existing PRDs."
)
@click.option(
    "--debug", is_flag=True, help="Output all prompts and results for debugging."
)
@click.pass_context
def normalize(ctx, input_file, yes, debug):
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

    click.echo("🔄 Normalizing specs...")
    normalize_prd(
        agent=ctx.obj["agent"],
        input_file=input_file,
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
def infra(ctx):
    """Phase 7: Infrastructure reconciliation. Ensures services are reachable."""
    state = load_project_state()
    missing = check_dependencies("infra", state)
    if missing:
        click.echo(
            f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first."
        )
        return

    if not INFRA.exists():
        if INFRA_SPEC.exists():
            click.echo(f"❌ {INFRA} not found, but {INFRA_SPEC} exists.")
            click.echo("   Run 'vibe normalize' to generate the required YAML file.")
        else:
            click.echo(
                f"❌ {INFRA} not found. Please create it manually or via 'vibe architect' + 'vibe normalize'."
            )
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
        "Set up or update environment variables as needed.",
    ]

    if loop.run():
        state["phases"]["infra"]["status"] = "completed"
        save_project_state(state)
        click.echo("✅ Infrastructure reconciliation and verification complete.")
        click.echo("\nNext Steps:")
        click.echo("[ ] Setup CI/CD (vibe cicd)")
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
    """Phase 6: Testing reconciliation. Ensures integration and regression tests pass."""
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
        click.echo("[ ] Setup Infrastructure (vibe infra)")
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


if __name__ == "__main__":
    cli()
