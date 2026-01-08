import pathlib

import click

from vibe_tools.setup import maybe_init_git
from vibe_tools.templates import TEMPLATES
from vibe_tools.utils import (
    COSTS_DIR,
    INSTRUCTIONS_DIR,
    LOGS_DIR,
    PRD_DIR,
    VIBE_DATA_DIR,
    VIBE_PROJECT_DIR,
    ensure_dir,
    ensure_gitignore,
    ensure_project_structure,
    migrate_to_project_dir,
)


def _perform_basic_init():
    """Helper to initialize the project structure and essential templates."""
    maybe_init_git()

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


def register_init(cli):
    @click.command()
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
            # Get setup command from cli
            setup_cmd = cli.get_command(ctx, "setup")
            if setup_cmd:
                ctx.invoke(setup_cmd, import_code=True)
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

    cli.add_command(init)

    cli.add_command(init)
