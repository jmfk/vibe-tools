import json
import pathlib

import click

from vibe_tools.setup import guide_setup
from vibe_tools.utils import (
    perform_basic_init,
)


def register_init(cli):
    @click.command()
    @click.pass_context
    def init(ctx):
        """Interactive guided project initialization."""
        if not guide_setup():
            click.echo(
                click.style(
                    "\n❌ Initialization aborted due to missing prerequisites.",
                    fg="red",
                )
            )
            return

        click.echo(
            click.style("\n=== VIBE PROJECT INITIALIZATION ===", fg="cyan", bold=True)
        )
        click.echo(
            "Welcome! Let's get your project set up for automated development.\n"
        )

        click.echo("Please select your starting scenario:")
        click.echo(
            click.style("  A) Human Planning", bold=True)
            + " - You already have human-written markdown specs in 'product/'."
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
        perform_basic_init()

        if choice == "A":
            click.echo(
                "\n📄 Basic initialization complete. Your human specs should be in 'product/'."
            )
        elif choice == "B":
            click.echo("\n🔍 Starting codebase discovery...")
            # Get setup command from cli
            setup_cmd = cli.get_command(ctx, "setup")
            if setup_cmd:
                ctx.invoke(setup_cmd, import_code=True)
        elif choice == "C":
            click.echo(
                "\n🏗️  Basic initialization complete. 'architecture.yaml' is ready."
            )
        else:
            click.echo("\n✅ Basic initialization complete.")

        click.echo("\nNext Steps:")
        click.echo(
            f"  {click.style('vibe architect', fg='cyan'):<20} Phase 1: Refine architecture and infrastructure"
        )
        click.echo(
            f"  {click.style('vibe pm', fg='magenta'):<20} Phase 1: Refine PRDs and product specs"
        )
        click.echo("\nRun 'vibe status' at any time to see your project progress.")

    cli.add_command(init)
