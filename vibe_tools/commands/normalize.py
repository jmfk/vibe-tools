import pathlib

import click

from vibe_tools.setup import maybe_init_git
from vibe_tools.utils import (
    ARCHITECTURE_SPEC,
    CICD_SPEC,
    DEV_SPEC,
    INFRA_SPEC,
    OVERVIEW_SPEC,
    TESTING_SPEC,
    check_dependencies,
    load_project_state,
    get_prd_inconsistencies,
    fix_prd_inconsistencies,
)


def register_normalize(cli):
    @click.command()
    @click.option(
        "--yes", "-y", is_flag=True, help="Automatically overwrite existing PRDs."
    )
    @click.option(
        "--debug", is_flag=True, help="Output all prompts and results for debugging."
    )
    @click.pass_context
    def normalize(ctx, yes, debug):
        """Phase 2: Normalize human-written PRDs from product/ into machine-consumable YAML in prds/."""
        maybe_init_git()
        state = load_project_state()

        # Check for PRD location inconsistencies
        inconsistencies = get_prd_inconsistencies()
        if inconsistencies:
            click.echo("⚠️  Found PRD location inconsistencies:")
            for inc in inconsistencies:
                click.echo(
                    f"  - {inc['name']}: MD at {inc['md_path']}, YAML at {inc['yaml_path']}"
                )

            if yes or click.confirm(
                "Fix inconsistencies to synchronize MD and YAML locations?",
                default=True,
            ):
                fix_prd_inconsistencies(inconsistencies, prefer_yaml=False)
                click.echo("✅ Inconsistencies fixed.")
                # Reload state after fixing
                state = load_project_state()
            else:
                click.echo("❌ Aborted. Please fix inconsistencies manually.")
                return

        missing = check_dependencies("normalize", state)
        if missing:
            click.echo(
                f"❌ Dependencies not met: {', '.join(missing)}. Please complete them first."
            )
            return

        from vibe_tools.normalize import normalize_prd, normalize_system_file

        # Map special file names to their spec paths
        special_files = {
            "infrastructure": INFRA_SPEC,
            "architecture": ARCHITECTURE_SPEC,
            "cicd": CICD_SPEC,
            "testing": TESTING_SPEC,
            "build": DEV_SPEC,
            "dev_environment": DEV_SPEC,
            "project-overview": OVERVIEW_SPEC,
            "project_overview": OVERVIEW_SPEC,
        }

        click.echo("🔄 Normalizing system files...")
        for file_to_normalize in special_files:
            normalize_system_file(
                agent=ctx.obj["agent"],
                input_file=special_files[file_to_normalize],
                auto_overwrite=yes,
                caffeinate=ctx.obj.get("caffeinate", False),
                stream=ctx.obj.get("stream", False),
                debug=debug,
            )
        # No files specified, normalize all files in product/
        click.echo("🔄 Normalizing PRDs...")
        normalize_prd(
            agent=ctx.obj["agent"],
            input_file=None,
            auto_overwrite=yes,
            caffeinate=ctx.obj.get("caffeinate", False),
            stream=ctx.obj.get("stream", False),
            debug=debug,
        )

        click.echo("\nNext Steps:")
        click.echo(
            "[ ] Review/Edit generated YAMLs in implementation/ and implementation/prds/"
        )
        click.echo("[ ] Architecture Setup (vibe setup)")
        click.echo("[ ] Install Dependencies (vibe deps)")
        click.echo("[ ] Start Building (vibe implement)")

    cli.add_command(normalize)
