import pathlib
import click
import json
import subprocess
from vibe_tools.utils import ensure_dir, ensure_gitignore, is_merged, run_command
from vibe_tools.templates import TEMPLATES

CONFIG_FILE = pathlib.Path(".vibe_config.json")
STATE_FILE = pathlib.Path(".ralph_state.json")


def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_config(config):
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    ensure_gitignore(".vibe_config.json")


def maybe_init_git():
    from vibe_tools.utils import is_git_repo

    if not is_git_repo():
        if click.confirm(
            "\nNo git repository found. Would you like to initialize one?", default=True
        ):
            try:
                subprocess.run(["git", "init"], check=True)
                click.echo("✅ Initialized empty Git repository.")
                ensure_gitignore(".vibe_config.json")
            except Exception as e:
                click.echo(f"❌ Failed to initialize Git repository: {e}")


@click.group(invoke_without_command=True)
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
def cli(ctx, agent, caffeinate):
    ctx.ensure_object(dict)
    ctx.obj["agent"] = agent

    config = load_config()
    if caffeinate is None:
        caffeinate = config.get("caffeinate", False)
    ctx.obj["caffeinate"] = caffeinate

    if ctx.invoked_subcommand is None:
        click.echo("vibe-tools configuration:")
        click.echo(f"  Agent: {agent}")
        click.echo(f"  Caffeinate: {'ON' if caffeinate else 'OFF'}")

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

        click.echo("\nAvailable commands:")
        for command in sorted(cli.list_commands(ctx)):
            cmd_obj = cli.get_command(ctx, command)
            click.echo(f"  {command:<10} {cmd_obj.get_short_help_str()}")

        click.echo("\nRun 'vibe --help' for full options.")


@cli.command()
def init():
    """Initialize the prompts directory and default templates."""
    maybe_init_git()
    prompts_dir = pathlib.Path("prompts")
    ensure_dir(prompts_dir)

    for filename, content in TEMPLATES.items():
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
    "--auto-merge/--no-auto-merge",
    is_flag=True,
    default=None,
    help="Enable/disable automatic merge.",
)
@click.pass_context
def ralph(ctx, review, tests, auto_merge):
    """Run the Ralph loop for processing PRDs."""
    maybe_init_git()
    agent = ctx.obj.get("agent", "cursor-agent")
    config = load_config().get("ralph", {})

    # Use config if not explicitly provided via CLI
    if review is None:
        review = config.get("review", False)
    if tests is None:
        tests = config.get("tests", False)
    if auto_merge is None:
        auto_merge = config.get("auto_merge", False)

    # If everything is still False (and we have no config file), prompt the user
    if not CONFIG_FILE.exists() and not any([review, tests, auto_merge]):
        click.echo("\n⚠️ Ralph is not yet configured for quality gates.")
        
        tests = click.confirm(
            "Enable Tests (auto-discover backend and frontend tests)?",
            default=True,
        )
        if tests:
            click.echo("✅ Tests enabled.")

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
                        "auto_merge": auto_merge,
                    },
                    "caffeinate": caffeinate,
                }
            )
            click.echo("✅ Configuration saved.")

    click.echo("\n--- Ralph Loop Configuration ---")
    click.echo(f"Agent:      {agent}")
    click.echo(f"Review:     {'ON' if review else 'OFF'}")
    click.echo(f"Tests:      {'ON' if tests else 'OFF'}")
    click.echo(f"Auto-merge: {'ON' if auto_merge else 'OFF'}")

    click.echo("\nWorkflow:")
    click.echo("1. Ensure 'main' branch.")
    click.echo("2. Sequentially process all 'prd_*.yaml' in 'prds/'.")
    click.echo(
        "3. Create feature branch, run up to 10 agent iterations for implementation."
    )
    click.echo("4. Run quality gates (tests/review) if enabled.")
    click.echo("5. Commit and optionally merge changes.")

    if not click.confirm("\nProceed with Ralph loop?", default=True):
        click.echo("Aborted.")
        return

    from vibe_tools.ralph import ralph_loop

    ralph_loop(
        agent=agent,
        review=review,
        tests=tests,
        auto_merge=auto_merge,
        caffeinate=ctx.obj.get("caffeinate", False),
    )


@cli.command()
@click.pass_context
def test_fix(ctx):
    """Run the test and fix loop."""
    from vibe_tools.test_fix import test_fix_loop

    test_fix_loop(agent=ctx.obj["agent"], caffeinate=ctx.obj.get("caffeinate", False))


@cli.command()
@click.pass_context
def coverage(ctx):
    """Run the coverage improvement loop."""
    from vibe_tools.coverage import improve_coverage_loop

    improve_coverage_loop(
        agent=ctx.obj["agent"], caffeinate=ctx.obj.get("caffeinate", False)
    )


@cli.command()
@click.pass_context
def history(ctx):
    """List all PRDs and their current status."""
    maybe_init_git()
    prd_dir = pathlib.Path("prds")
    if not prd_dir.exists():
        click.echo("PRD directory 'prds/' not found.")
        return

    prds = sorted(prd_dir.glob("prd_*.yaml"))
    if not prds:
        click.echo("No PRD files found in 'prds/'.")
        return

    click.echo("\nPRD Status History:")
    click.echo(f"{'ID':<5} {'PRD Name':<40} {'Status':<15}")
    click.echo("-" * 65)

    for prd_file in prds:
        project_name = prd_file.stem
        # Extract ID if possible (e.g., prd_00 -> 00)
        prd_id = project_name.split("_")[1] if "_" in project_name else "??"
        branch_name = f"feature/{project_name}"

        # Determine status
        if is_merged(branch_name):
            status = "✅ COMPLETED"
        else:
            _, check_branch = run_command(
                ["git", "rev-parse", "--verify", branch_name], check=False
            )
            if check_branch == 0:
                status = "⏳ IN_PROGRESS"
            else:
                status = "⚪️ PENDING"

        click.echo(f"{prd_id:<5} {project_name:<40} {status:<15}")
    click.echo("")


@cli.command()
@click.argument("prd_identifier")
@click.option("--force", "-f", is_flag=True, help="Don't ask for confirmation.")
@click.pass_context
def rerun(ctx, prd_identifier, force):
    """Set a PRD to be rerun by resetting its branch and state."""
    maybe_init_git()
    prd_dir = pathlib.Path("prds")
    if not prd_dir.exists():
        click.echo("PRD directory 'prds/' not found.")
        return

    # Find the PRD file
    prds = list(prd_dir.glob("prd_*.yaml"))
    target_prd = None

    # Try exact match, then by ID
    for prd in prds:
        if prd.stem == prd_identifier or (
            "_" in prd.stem and prd.stem.split("_")[1] == prd_identifier
        ):
            target_prd = prd
            break

    if not target_prd:
        click.echo(f"Could not find PRD matching '{prd_identifier}'.")
        return

    project_name = target_prd.stem
    branch_name = f"feature/{project_name}"

    click.echo(f"Resetting state for: {project_name}")

    # Check branch status
    if is_merged(branch_name):
        click.echo(f"⚠️  Warning: Branch '{branch_name}' is already merged into main.")
        if not force and not click.confirm("Are you sure you want to rerun it?", default=False):
            click.echo("Aborted.")
            return

    # Check if branch exists
    _, check_branch = run_command(
        ["git", "rev-parse", "--verify", branch_name], check=False
    )

    if check_branch == 0:
        if not force and not click.confirm(
            f"Branch '{branch_name}' exists. Delete it to rerun from scratch?", default=True
        ):
            click.echo("Aborted.")
            return

        # Delete branch
        current_branch, _ = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        if current_branch == branch_name:
            run_command(["git", "checkout", "main"])

        run_command(["git", "branch", "-D", branch_name])
        click.echo(f"✅ Deleted branch '{branch_name}'.")

    # Clear state if it belongs to this PRD
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
            if state.get("prd_name") == project_name:
                STATE_FILE.unlink()
                click.echo("✅ Cleared Ralph state for this PRD.")
        except Exception:
            pass

    click.echo(f"🚀 {project_name} is ready to be rerun with 'vibe ralph'.")


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


if __name__ == "__main__":
    cli()
