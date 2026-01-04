import atexit
import json
import logging
import pathlib
import subprocess
from typing import List

import click

from vibe_tools.cost import finalize_cost_report, get_total_cost
from vibe_tools.templates import TEMPLATES
from vibe_tools.utils import (
    COSTS_DIR,
    PRD_DIR,
    STATE_FILE,
    enable_console_debug,
    ensure_dir,
    ensure_gitignore,
    get_agent_command,
    get_google_api_key,
    load_config,
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


@click.group(invoke_without_command=True)
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
def cli(ctx, debug, verbose, agent, caffeinate):
    # Initialize logging for the invoked command
    command_name = ctx.invoked_subcommand or "info"
    setup_logging(command_name)

    # Register session cost reporting at exit
    atexit.register(finalize_cost_report)

    ctx.ensure_object(dict)
    ctx.obj["agent"] = agent

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
        click.echo(f"  Caffeinate: {'ON' if caffeinate else 'OFF'}")
        click.echo(f"  Verbose: {'ON' if verbose else 'OFF'}")
        click.echo(f"  Default Budget: ${default_budget:.2f} USD")

        ralph_config = config.get("ralph", {})
        if ralph_config:
            click.echo("  Ralph Default Config:")
            click.echo(
                f"    Tests:      {'ON' if ralph_config.get('tests') else 'OFF'}"
            )
            click.echo(
                f"    Review:     {'ON' if ralph_config.get('review') else 'OFF'}"
            )
            click.echo(
                f"    Auto-merge: {'ON' if ralph_config.get('auto_merge') else 'OFF'}"
            )
        else:
            click.echo("  Ralph Default Config: Not set (will prompt on first run)")

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
        for command in sorted(cli.list_commands(ctx)):
            cmd_obj = cli.get_command(ctx, command)
            if cmd_obj:
                click.echo(f"  {command:<10} {cmd_obj.get_short_help_str()}")

        click.echo("\nRun 'vibe --help' for full options.")


@cli.command()
def init():
    """Initialize the prompts directory and default templates."""
    maybe_init_git()
    ensure_gitignore("logs/")
    prompts_dir = pathlib.Path("prompts")
    ensure_dir(prompts_dir)

    # Create new directories for instructions and specs
    from vibe_tools.utils import INSTRUCTIONS_DIR

    ensure_dir(INSTRUCTIONS_DIR)
    ensure_dir(pathlib.Path("specs") / "infra")
    ensure_dir(pathlib.Path("specs") / "cicd")
    ensure_dir(pathlib.Path("prds"))

    for filename, content in TEMPLATES.items():
        if filename in ["dummy_backend_test", "dummy_frontend_test"]:
            continue

        if filename == "Makefile":
            file_path = pathlib.Path(filename)
        else:
            file_path = prompts_dir / filename

        if not file_path.exists():
            print(f"Creating template: {file_path}")
            file_path.write_text(content)
        else:
            print(f"Template already exists: {file_path}")


@cli.command()
@click.option(
    "--review/--no-review",
    is_flag=True,
    default=None,
    help="Enable/disable agentic review.",
)
@click.option(
    "--tests/--no-tests",
    is_flag=True,
    default=None,
    help="Enable/disable running tests.",
)
@click.option(
    "--coverage/--no-coverage",
    is_flag=True,
    default=None,
    help="Enable/disable coverage enforcement.",
)
@click.option(
    "--auto-merge/--no-auto-merge",
    is_flag=True,
    default=None,
    help="Enable/disable automatic merge.",
)
@click.option(
    "--fast/--no-fast",
    is_flag=True,
    default=None,
    help="Only run tests for changed files (more efficient).",
)
@click.option(
    "--budget",
    type=float,
    default=None,
    help="Max budget in USD for this run. System will pause if reached.",
)
@click.pass_context
def ralph(ctx, review, tests, coverage, auto_merge, fast, budget):
    """Run the Ralph loop for processing PRDs."""
    maybe_init_git()
    agent = ctx.obj.get("agent", "cursor-agent")
    config = load_config().get("ralph", {})

    # Use config if not explicitly provided via CLI
    if review is None:
        review = config.get("review", False)
    if tests is None:
        tests = config.get("tests", False)
    if coverage is None:
        coverage = config.get("coverage", False)
    if auto_merge is None:
        auto_merge = config.get("auto_merge", False)
    if fast is None:
        fast = config.get("fast", False)
    if budget is None:
        budget = config.get("budget")
    if budget is None:
        budget = ctx.obj.get("default_budget", 5.0)

    # If everything is still False (and we have no config file), prompt the user
    if not CONFIG_FILE.exists() and not any([review, tests, coverage, auto_merge]):
        click.echo("\n⚠️ Ralph is not yet configured for quality gates.")

        tests = click.confirm(
            "Enable Tests (auto-discover backend and frontend tests)?",
            default=True,
        )
        if tests:
            click.echo("✅ Tests enabled.")

            fast = click.confirm(
                "Enable Fast Mode (only run tests for changed files)?",
                default=True,
            )
            if fast:
                click.echo("✅ Fast mode enabled.")

            coverage = click.confirm(
                "Enable Coverage Enforcement (ensure 85%+ coverage)?",
                default=True,
            )
            if coverage:
                click.echo("✅ Coverage Enforcement enabled.")

        review = click.confirm(
            "Enable Agentic Review (agent verifies changes against PRD)?",
            default=True,
        )
        if review:
            click.echo("✅ Agentic Review enabled.")

        auto_merge = click.confirm(
            "Enable Auto-merge (automatically merge into main if quality gates pass)?",
            default=False,
        )
        if auto_merge:
            click.echo("✅ Auto-merge enabled.")

        budget = click.prompt(
            "Set a max budget in USD for this run?",
            type=float,
            default=5.0,
        )
        click.echo(f"✅ Budget set to ${budget:.2f} USD.")

        verbose = click.confirm(
            "Enable verbose output (log prompts and commands to terminal)?",
            default=False,
        )
        if verbose:
            click.echo("✅ Verbose output enabled.")

        caffeinate = ctx.obj.get("caffeinate", False)
        if not caffeinate:
            if click.confirm(
                "Would you like to use 'caffeinate' to prevent system sleep during long runs?",
                default=True,
            ):
                caffeinate = True
                ctx.obj["caffeinate"] = caffeinate
                click.echo("✅ Enabled Caffeinate.")

        if click.confirm(
            "Save these settings as default in .vibe_config.json?", default=True
        ):
            save_config(
                {
                    "ralph": {
                        "review": review,
                        "tests": tests,
                        "coverage": coverage,
                        "auto_merge": auto_merge,
                        "fast": fast,
                    },
                    "default_budget": budget,
                    "caffeinate": caffeinate,
                    "verbose": verbose,
                    "coverage_targets": {
                        "backend": 85,
                        "frontend": 85,
                        "infra": 85,
                    },
                }
            )
            click.echo("✅ Configuration saved.")

    click.echo("\n--- Ralph Loop Configuration ---")
    click.echo(f"Agent:      {agent}")
    click.echo(f"Review:     {'ON' if review else 'OFF'}")
    click.echo(f"Tests:      {'ON' if tests else 'OFF'}")
    click.echo(f"Coverage:   {'ON' if coverage else 'OFF'}")
    click.echo(f"Fast Mode:  {'ON' if fast else 'OFF'}")
    click.echo(f"Auto-merge: {'ON' if auto_merge else 'OFF'}")
    click.echo(f"Max Budget: ${budget:.2f} USD")

    click.echo("\nWorkflow:")
    click.echo("1. Ensure 'main' branch.")
    click.echo("2. Sequentially process all 'prd_*.yaml' in 'prds/'.")
    click.echo(
        "3. Create feature branch, run up to 10 agent iterations for implementation."
    )
    click.echo("4. Run quality gates (tests/review) if enabled.")
    click.echo("5. Commit and optionally merge changes.")

    from vibe_tools.ralph import get_pending_prds_and_estimates, ralph_loop

    # Get estimates for pending PRDs
    vibe_config = load_config()
    pending_estimates = get_pending_prds_and_estimates(agent, vibe_config)

    if pending_estimates:
        click.echo("\nPending PRDs and Estimated Initial Costs:")
        total_initial_cost = 0.0
        for est in pending_estimates:
            resume_suffix = " [RESUMING]" if est["is_resume"] else ""
            click.echo(
                f"  - {est['prd_name']}{resume_suffix} (Model: {est['model']}, Est. Initial Cost: ${est['cost_estimate']:.6f})"
            )
            total_initial_cost += est["cost_estimate"]

        click.echo(f"\nTotal Estimated Initial Cost: ${total_initial_cost:.6f} USD")
        click.echo(
            "(Note: Subsequent iterations and output tokens will incur additional costs.)"
        )

        if total_initial_cost > budget:
            click.echo(
                f"\n⚠️ WARNING: Estimated cost (${total_initial_cost:.6f}) exceeds current budget (${budget:.2f})!"
            )
    else:
        click.echo("\nNo pending PRDs found to process.")

    if not click.confirm("\nProceed with Ralph loop?", default=True):
        click.echo("Aborted.")
        return

    ralph_loop(
        agent=agent,
        review=review,
        tests=tests,
        coverage=coverage,
        auto_merge=auto_merge,
        caffeinate=ctx.obj.get("caffeinate", False),
        budget=budget,
        fast=fast,
    )


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
    )


@cli.command()
@click.pass_context
def coverage(ctx):
    """Run the coverage improvement loop."""
    from vibe_tools.coverage import improve_coverage_loop

    improve_coverage_loop(
        agent=ctx.obj["agent"], caffeinate=ctx.obj.get("caffeinate", False)
    )


@cli.command()
@click.argument("input_file", required=False)
@click.option(
    "--yes", "-y", is_flag=True, help="Automatically overwrite existing PRDs."
)
@click.pass_context
def normalize(ctx, input_file, yes):
    """Normalize human-written PRDs from specs/ into machine-consumable YAML in prds/."""
    maybe_init_git()
    from vibe_tools.normalize import normalize_prd

    normalize_prd(
        agent=ctx.obj["agent"],
        input_file=input_file,
        auto_overwrite=yes,
        caffeinate=ctx.obj.get("caffeinate", False),
    )


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

    run_monitor(agent=ctx.obj["agent"], interval=interval)


@cli.command(name="review-prd")
@click.option(
    "--review/--no-review",
    type=bool,
    default=True,
    help="Run the agentic review prompt after showing the PRD.",
)
@click.pass_context
def review_prd(ctx, review):
    """[DEPRECATED] List specs PRDs, display one, and optionally run the Gemini review prompt."""
    click.echo(
        "⚠️ 'review-prd' is deprecated. 'vibe prd' now includes a /review command during creation."
    )
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
    agent_type: str, prd_path: pathlib.Path, caffeinate: bool
) -> None:
    if not REVIEW_PROMPT_TEMPLATE.exists():
        click.echo("Review prompt template missing; skipping agentic review.")
        return

    prompt_text = REVIEW_PROMPT_TEMPLATE.read_text().format(prd_path=prd_path)
    command = get_agent_command(agent_type, prompt_text)
    output, exit_code = run_agent(command, caffeinate=caffeinate)

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

    # Target dir based on type
    target_specs_dir = specs_base
    if type in ["infra", "cicd"]:
        target_specs_dir = specs_base / type
        ensure_dir(target_specs_dir)

    writer = InteractivePRD(
        agent_type=ctx.obj.get("agent", "cursor-agent"),
        specs_dir=target_specs_dir,
        prd_type=type,
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
    """[DEPRECATED] Use 'vibe prd' instead. Runs the legacy dspy interview loop."""
    click.echo(
        "⚠️ 'write-prd' is deprecated. Please use 'vibe prd' for the new interactive experience."
    )
    from vibe_tools.prd_writer import PRDWriter

    initial_prompt = title or click.prompt(
        f"Describe the {type} PRD you'd like to write"
    )

    # Base specs dir
    specs_base = pathlib.Path("specs")
    ensure_dir(specs_base)

    # Target dir based on type
    target_specs_dir = specs_base
    if type in ["infra", "cicd"]:
        target_specs_dir = specs_base / type
        ensure_dir(target_specs_dir)

    writer = PRDWriter(
        agent_type=ctx.obj.get("agent", "cursor-agent"),
        specs_dir=target_specs_dir,
        prd_type=type,
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

    from vibe_tools.ralph import load_state

    state = load_state()
    completed_prds = state.get("completed_prds", [])
    started_prds = state.get("started_prds", [])

    for prd_file in prds:
        # Show relative path for infra/cicd
        try:
            project_name = prd_file.relative_to(PRD_DIR).with_suffix("").as_posix()
        except ValueError:
            project_name = prd_file.stem

        if prd_file.stem in completed_prds:
            status = "✅ DONE"
        elif prd_file.stem in started_prds:
            status = "⏳ IN_PROGRESS"
        else:
            status = "⚪️ PENDING"

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

    content = TEMPLATES.get("README", "Documentation not found in templates.")
    click.echo_via_pager(content)


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
def cleanup():
    """Clean up stale pytest, cursor-agent, and caffeinate processes."""
    from vibe_tools.utils import cleanup_stale_processes

    cleanup_stale_processes()


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
    from vibe_tools.ralph import load_state

    state = load_state()
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
        STATE_FILE.write_text(json.dumps(state, indent=2))

    # 2. Delete the branch if it exists
    _, check_branch = run_command(
        ["git", "rev-parse", "--verify", branch_name], check=False
    )
    if check_branch == 0:
        # Check if we are currently on that branch
        stdout, _ = run_command(["git", "branch", "--show-current"], check=False)
        if stdout.strip() == branch_name:
            click.echo(f"Currently on branch {branch_name}. Switching to main...")
            run_command(["git", "checkout", "main"])

        # Delete branch
        _, code = run_command(["git", "branch", "-D", branch_name], check=False)
        if code == 0:
            click.echo(f"✅ Deleted branch {branch_name}.")
        else:
            click.echo(f"❌ Failed to delete branch {branch_name}.")
    else:
        click.echo(f"Branch {branch_name} does not exist. Nothing to delete.")

    click.echo(f"\nReady to rerun: 'vibe ralph' will now pick up {project_name} again.")


if __name__ == "__main__":
    cli()
