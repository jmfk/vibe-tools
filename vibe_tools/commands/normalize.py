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
)


def register_normalize(cli):
    @click.command()
    @click.argument("input_files", nargs=-1, required=False)
    @click.option(
        "--yes", "-y", is_flag=True, help="Automatically overwrite existing PRDs."
    )
    @click.option(
        "--debug", is_flag=True, help="Output all prompts and results for debugging."
    )
    @click.pass_context
    def normalize(ctx, input_files, yes, debug):
        """Phase 2: Normalize human-written PRDs from product/ into machine-consumable YAML in prds/."""
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
            "build": DEV_SPEC,
            "dev_environment": DEV_SPEC,
            "project-overview": OVERVIEW_SPEC,
            "project_overview": OVERVIEW_SPEC,
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
            # No files specified, normalize all files in product/
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
        click.echo("[ ] Review/Edit generated YAMLs in implementation/prds/")
        click.echo("[ ] Architecture Setup (vibe setup)")
        click.echo("[ ] Install Dependencies (vibe deps)")
        click.echo("[ ] Start Building (vibe implement)")
