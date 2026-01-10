import pathlib
import shutil

import click

from vibe_tools.utils import (
    BACKLOG_DIR,
    HISTORY_DIR,
    PLANNING_BACKLOG_DIR,
    PLANNING_HISTORY_DIR,
    PRODUCT_DIR,
    PROJECT_STATE_FILE,
    ensure_project_structure,
    load_project_state,
    logger,
)


def register_migrate(cli):
    @click.command()
    def migrate():
        """Migrate existing PRDs to the new folder structure (inbox/backlog/history)."""
        click.echo("🚀 Starting migration to new structure...")

        ensure_project_structure()

        # 1. Handle project -> implementation and specs -> product migration
        from vibe_tools.utils import migrate_to_project_dir
        migrate_to_project_dir()

        state = load_project_state()
        completed_prds = set(state.get("completed_prds", []))

        # 2. Migrate from implementation/prds/ (previously project/prds/)
        old_prd_dir = pathlib.Path("implementation/prds")
        if old_prd_dir.exists() and old_prd_dir.is_dir():
            for yaml_file in old_prd_dir.glob("*.yaml"):
                # Determine if it's completed
                # yaml files are usually prd_xxx.yaml
                prd_id = yaml_file.stem
                if prd_id.startswith("prd_"):
                    prd_id = prd_id[4:]

                # Move YAML files to backlog/history if they are directly in prds/
                target_dir = HISTORY_DIR if prd_id in completed_prds else BACKLOG_DIR
                target_path = target_dir / yaml_file.name

                if not target_path.exists():
                    click.echo(f"  Moving {yaml_file} to {target_dir}/")
                    shutil.copy2(yaml_file, target_path)
                    yaml_file.unlink() # Cleanup after move if it was in the root of prds/
                else:
                    if yaml_file.parent == old_prd_dir: # Only unlink if it's in the root
                         click.echo(f"  Skipping {yaml_file}, already exists in {target_dir}/")

        # 3. Migrate from product/ (previously specs/)
        if PRODUCT_DIR.exists() and PRODUCT_DIR.is_dir():
            for md_file in PRODUCT_DIR.glob("*.md"):
                # Only move if it matches a PRD pattern or we want to organize them
                # Architecture and Infra stay in root of product/
                if md_file.name in ["architecture.md", "infrastructure.md", "cicd.md", "testing.md", "build.md"]:
                    continue
                
                # Check if it should go to history or backlog
                prd_id = md_file.stem
                # Clean prd_ prefix for check
                clean_id = prd_id.lower()
                if clean_id.startswith("prd-") or clean_id.startswith("prd_"):
                     clean_id = clean_id[4:]
                
                target_dir = PLANNING_HISTORY_DIR if clean_id in completed_prds else PLANNING_BACKLOG_DIR
                target_path = target_dir / md_file.name

                if not target_path.exists():
                    click.echo(f"  Moving {md_file} to {target_dir}/")
                    shutil.copy2(md_file, target_path)
                    md_file.unlink()
                else:
                    if md_file.parent == PRODUCT_DIR:
                        click.echo(f"  Skipping {md_file}, already exists in {target_dir}/")
        
        click.echo("✅ Migration complete.")

    cli.add_command(migrate)
