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
        from vibe_tools.utils import get_file_hash, safe_yaml_load, VIBE_PROJECT_DIR
        import re

        # Unique system specs to normalize
        system_specs = [
            ARCHITECTURE_SPEC,
            OVERVIEW_SPEC,
            INFRA_SPEC,
            CICD_SPEC,
            TESTING_SPEC,
            DEV_SPEC,
        ]

        # Pre-check system files status
        to_normalize = []
        already_up_to_date = []
        for spec_path in system_specs:
            if not spec_path.exists():
                continue
            
            stem = spec_path.stem
            clean_stem = re.sub(r"[- ]", "_", stem.lower())
            output_path = VIBE_PROJECT_DIR / f"{clean_stem}.yaml"
            
            if not output_path.exists():
                to_normalize.append(spec_path)
                continue
                
            md_hash = get_file_hash(spec_path)
            try:
                existing_data = safe_yaml_load(output_path.read_text())
                if existing_data and isinstance(existing_data, dict):
                    old_hash = existing_data.get("METADATA", {}).get("SOURCE_HASH")
                    if old_hash == md_hash:
                        already_up_to_date.append(spec_path)
                    else:
                        to_normalize.append(spec_path)
                else:
                    to_normalize.append(spec_path)
            except Exception:
                to_normalize.append(spec_path)

        overwrite_mode = yes
        if not to_normalize and already_up_to_date and not yes:
            choice = click.prompt(
                f"All {len(already_up_to_date)} system files are up-to-date. Reprocess? [y]es, [n]o, [a]sk per file",
                type=click.Choice(["y", "n", "a"], case_sensitive=False),
                default="n",
            )
            if choice.lower() == "y":
                to_normalize = already_up_to_date
                overwrite_mode = True
            elif choice.lower() == "a":
                to_normalize = already_up_to_date
                overwrite_mode = "ask"
            else:
                to_normalize = []

        if to_normalize:
            click.echo("🔄 Normalizing system files...")
            for spec_path in to_normalize:
                overwrite_mode = normalize_system_file(
                    agent=ctx.obj["agent"],
                    input_file=spec_path,
                    auto_overwrite=overwrite_mode,
                    caffeinate=ctx.obj.get("caffeinate", False),
                    stream=ctx.obj.get("stream", False),
                    debug=debug,
                    force=True if (overwrite_mode is True or overwrite_mode == "yes") else False
                )
        else:
            click.echo("✅ System files are up-to-date.")

        # No files specified, normalize all files in product/
        click.echo("🔄 Normalizing PRDs...")
        normalize_prd(
            agent=ctx.obj["agent"],
            input_file=None,
            auto_overwrite=overwrite_mode,
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
