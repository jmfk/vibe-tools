import pathlib
import shutil
import json
import re
import click
from typing import Dict, List, Set

from vibe_tools.utils import (
    PRODUCT_DIR,
    PRODUCT_BACKLOG_DIR,
    PRODUCT_IN_PROGRESS_DIR,
    PRODUCT_HISTORY_DIR,
    PRD_DIR,
    PRD_DONE_DIR,
    PRD_FAILED_DIR,
    PRD_PROCESSING_DIR,
    VIBE_PROJECT_DIR,
    PROJECT_STATE_FILE,
    ensure_project_structure,
    load_project_state,
    save_project_state,
    safe_yaml_load,
    collect_all_prd_info,
)
from vibe_tools.prds import PRD, load_prd


def full_migration_needed(prd: PRD) -> bool:
    """Checks if a PRD needs a full migration (missing fields)."""
    return not (prd.id and prd.type and prd.status)


def run_reconciliation(quiet=False):
    """Unified migration to PRD-NNN scheme in product/ directory."""
    ISSUES_DIR = pathlib.Path("issues")
    if not quiet:
        click.echo("🚀 Starting unified PRD migration...")

    ensure_project_structure()

    # 1. Collect all initiatives
    all_prds: List[PRD] = []
    
    # 1a. Migrate Legacy Issues
    if ISSUES_DIR.exists():
        if not quiet: click.echo("📋 Migrating legacy issues...")
        for issue_file in ISSUES_DIR.rglob("ISSUE-*.md"):
            try:
                # We use the old Issue.from_markdown logic indirectly via PRD.from_markdown
                # which I've updated to handle legacy frontmatter
                prd = PRD.from_markdown(issue_file.read_text(), path=issue_file)
                prd.type = "ISSUE"
                if "history" in str(issue_file):
                    prd.status = "done"
                all_prds.append(prd)
            except Exception as e:
                if not quiet: click.echo(f"  ⚠️  Failed to load issue {issue_file.name}: {e}")

    # 1b. Migrate Legacy PRDs (Markdown)
    legacy_md_dirs = [
        PRODUCT_DIR / "backlog",
        PRODUCT_DIR / "inbox",
        PRODUCT_DIR / "history",
        PRODUCT_DIR / "rejected"
    ]
    if not quiet: click.echo("📁 Migrating legacy markdown PRDs...")
    for md_dir in legacy_md_dirs:
        if not md_dir.exists(): continue
        for md_file in md_dir.glob("*.md"):
            # Avoid system files
            if md_file.stem in ["architecture", "infrastructure", "cicd", "testing", "dev_environment", "setup", "project_overview"]:
                continue
            
            try:
                prd = load_prd(md_file)
                
                # Enforce status based on directory even if skipping full migration
                if "history" in str(md_dir):
                    prd.status = "done"
                elif "backlog" in str(md_dir) or "inbox" in str(md_dir):
                    prd.status = "backlog"

                # If it already has a proper PRD-NNN ID and frontmatter, only re-process if missing core fields
                if prd.id and prd.id.startswith("PRD-") and prd.type and prd.status:
                    if not full_migration_needed(prd):
                        # Still save to update status if needed
                        prd.save()
                        continue
            except Exception as e:
                if not quiet: click.echo(f"  ⚠️  Failed to load PRD {md_file.name}: {e}")

    # 2. Build Dependency Graph and Sort
    # We want to assign IDs in a stable way, ideally topological or by date
    # For now, we'll sort by creation date or existing sequence if possible
    
    def sort_key(p: PRD):
        # Try to extract sequence from old PRD format v01-010
        match = re.search(r"v\d+-(\d+)", p.id)
        if match:
            return f"0-seq-{int(match.group(1)):06d}"
        # Issues usually have dates
        match = re.search(r"ISSUE-(\d{4}-\d{2}-\d{2})-(\d+)", p.id)
        if match:
            return f"1-date-{match.group(1)}-{int(match.group(2)):06d}"
        return f"2-time-{p.created_at}"

    all_prds.sort(key=sort_key)

    # 3. Assign New IDs and Map Dependencies
    id_map = {} # old_id -> new_id
    new_prds: List[PRD] = []
    
    for i, prd in enumerate(all_prds, 1):
        old_id = prd.id
        new_id = f"PRD-{i:03d}"
        id_map[old_id] = new_id
        prd.id = new_id
        new_prds.append(prd)

    # Update dependencies to use new IDs
    for prd in new_prds:
        new_deps = []
        for dep in prd.depends_on:
            if dep in id_map:
                new_deps.append(id_map[dep])
            elif f"prd_{dep}" in id_map:
                new_deps.append(id_map[f"prd_{dep}"])
            else:
                # Keep as is if not found
                new_deps.append(dep)
        prd.depends_on = new_deps

    # 4. Save to New Structure
    if not quiet: click.echo("💾 Saving migrated PRDs to product/...")
    for prd in new_prds:
        target_dir = PRODUCT_HISTORY_DIR if prd.status == "done" else PRODUCT_BACKLOG_DIR
        
        # Enforce status based on directory during migration
        if target_dir == PRODUCT_HISTORY_DIR:
            prd.status = "done"
        else:
            prd.status = "backlog"

        filename = f"{prd.id}-{re.sub(r'[^a-z0-9]+', '-', prd.title.lower())}.md"
        # Truncate filename if too long
        if len(filename) > 64:
            filename = filename[:60] + ".md"
        
        target_path = target_dir / filename
        prd.save(target_path)
        
        # If it was originally elsewhere, we'll cleanup later
        if not quiet: click.echo(f"  ✅ {prd.id} -> {target_path.relative_to(PRODUCT_DIR)}")

    # 5. Cleanup Old Files
    if not quiet: click.echo("🧹 Cleaning up old files...")
    
    # Remove old issues dir
    if ISSUES_DIR.exists():
        shutil.rmtree(ISSUES_DIR)
    
    # Remove old PRD directories in implementation/
    if PRD_DIR.exists():
        # Keep PRD_DIR but clear contents
        for item in PRD_DIR.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    # Clear old markdown files that were migrated
    for md_dir in legacy_md_dirs:
        if not md_dir.exists(): continue
        for md_file in md_dir.glob("*.md"):
            if not md_file.name.startswith("PRD-") and md_file.stem not in ["architecture", "infrastructure", "cicd", "testing", "dev_environment", "setup", "project_overview"]:
                md_file.unlink()

    # 6. Update state.json
    state = load_project_state()
    # Plans are now based on PRD-NNN IDs
    new_plans = {}
    completed_prds = []
    
    for prd in new_prds:
        new_plans[prd.id] = {
            "title": prd.title,
            "status": prd.status,
            "type": prd.type,
            "depends_on": prd.depends_on
        }
        if prd.status == "done":
            completed_prds.append(prd.id)
            
    state["plans"] = new_plans
    state["completed_prds"] = completed_prds
    state["next_sequence"] = len(new_prds) + 1
    save_project_state(state)

    if not quiet: click.echo("✅ Migration and reconciliation complete.")


def register_migrate(cli):
    @click.command()
    def migrate():
        """Migrate and reconcile project state with the filesystem and git."""
        run_reconciliation()

    cli.add_command(migrate)
