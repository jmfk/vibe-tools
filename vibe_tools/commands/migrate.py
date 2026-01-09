import pathlib
import shutil

import click

from vibe_tools.utils import (
    BACKLOG_DIR,
    HISTORY_DIR,
    PROJECT_STATE_FILE,
    ensure_project_structure,
    load_project_state,
    logger,
)


def register_migrate(cli):
    @click.command()
    def migrate():
        """Migrate existing PRDs to the new folder structure (inbox/backlog/history)."""
        click.echo("🚀 Starting migration to new PRD structure...")

        ensure_project_structure()

        state = load_project_state()
        completed_prds = set(state.get("completed_prds", []))

        # 1. Migrate from project/prds/
        old_prd_dir = pathlib.Path("project/prds")
        if old_prd_dir.exists() and old_prd_dir.is_dir():
            for yaml_file in old_prd_dir.glob("*.yaml"):
                # Determine if it's completed
                # yaml files are usually prd_xxx.yaml
                prd_id = yaml_file.stem
                if prd_id.startswith("prd_"):
                    prd_id = prd_id[4:]

                target_dir = HISTORY_DIR if prd_id in completed_prds else BACKLOG_DIR
                target_path = target_dir / yaml_file.name

                if not target_path.exists():
                    click.echo(f"  Moving {yaml_file} to {target_dir}/")
                    shutil.copy2(yaml_file, target_path)
                else:
                    click.echo(f"  Skipping {yaml_file}, already exists in {target_dir}/")

        # 2. Migrate from vibe-tools-prds/ (legacy if exists)
        legacy_dir = pathlib.Path("vibe-tools-prds")
        if legacy_dir.exists() and legacy_dir.is_dir():
            for md_file in legacy_dir.glob("*.md"):
                # For legacy MD files, we'll put them in backlog if not history
                # Usually these don't have exact matches in state.json unless they were normalized
                # We'll just put them in backlog for now as suggestions/planned work
                target_path = BACKLOG_DIR / md_file.name
                if not target_path.exists():
                    click.echo(f"  Moving legacy {md_file} to {BACKLOG_DIR}/")
                    shutil.copy2(md_file, target_path)

        click.echo("✅ Migration complete.")

    cli.add_command(migrate)
