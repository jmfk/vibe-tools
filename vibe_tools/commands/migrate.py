import pathlib
import shutil
import json
import yaml
import click

from vibe_tools.utils import (
    PRD_DIR,
    PRD_DONE_DIR,
    PRD_FAILED_DIR,
    PRD_PROCESSING_DIR,
    PLANNING_BACKLOG_DIR,
    PLANNING_HISTORY_DIR,
    PLANNING_INBOX_DIR,
    PLANNING_REJECTED_DIR,
    PRODUCT_DIR,
    ISSUES_DIR,
    ISSUES_BACKLOG_DIR,
    ISSUES_HISTORY_DIR,
    ISSUES_META_DIR,
    VIBE_PROJECT_DIR,
    PROJECT_STATE_FILE,
    ensure_project_structure,
    load_project_state,
    save_project_state,
    run_command,
    get_main_branch,
)

def run_reconciliation(quiet=False):
    """Core logic to migrate and reconcile project state with the filesystem and git."""
    if not quiet:
        click.echo("🚀 Starting comprehensive migration and reconciliation...")

    # First, migrate from root or legacy paths to the project directory
    from vibe_tools.utils import migrate_to_project_dir
    migrate_to_project_dir()

    ensure_project_structure()

    # 1. Load legacy data before it gets hidden by the new load_project_state
    old_state = {}
    if PROJECT_STATE_FILE.exists():
        try:
            old_state = json.loads(PROJECT_STATE_FILE.read_text())
        except Exception:
            pass

    old_index = {}
    index_file = ISSUES_META_DIR / "index.json"
    if index_file.exists():
        try:
            old_index = json.loads(index_file.read_text())
        except Exception:
            pass

    # 2. Migrate Issue metadata into frontmatter and move files
    if not quiet: click.echo("📋 Reconciling Issues...")
    all_issue_files = list(ISSUES_DIR.rglob("ISSUE-*.md"))
    from vibe_tools.issues import Issue
    
    for issue_file in all_issue_files:
        try:
            issue = Issue.from_markdown(issue_file.read_text())
            issue_id = issue.id
            
            # Enrich with index metadata if missing
            if issue_id in old_index:
                meta = old_index[issue_id]
                if not issue.github and meta.get("github_number"):
                    from vibe_tools.issues import GitHubInfo
                    issue.github = GitHubInfo(repo="", number=meta["github_number"], url="")
                if meta.get("updated_at") and not issue.updated_at:
                    issue.updated_at = meta["updated_at"]

            # Save to correct folder based on status
            from vibe_tools.issues import save_issue
            save_issue(issue)
            
            # Remove original if it was in a different place
            target_dir = ISSUES_HISTORY_DIR if issue.status == "done" else ISSUES_BACKLOG_DIR
            if issue_file.parent != target_dir:
                if not quiet: click.echo(f"  📦 Moving issue {issue_id} to {target_dir.name}")
                if issue_file.exists():
                    issue_file.unlink()
        except Exception as e:
            if not quiet: click.echo(f"  ⚠️  Failed to process issue {issue_file.name}: {e}")

    # 3. Migrate PRD metadata into YAMLs and move files
    if not quiet: click.echo("📁 Reconciling PRDs...")
    
    # Track which PRD IDs we've processed to avoid duplicates
    processed_prds = set()
    
    # Folders to scan for PRDs
    prd_scan_dirs = [
        PRD_DIR,
        PRD_PROCESSING_DIR,
        PRD_DONE_DIR,
        PRD_FAILED_DIR,
        PRD_DIR / "backlog", # Legacy
        PRD_DIR / "history", # Legacy
        PRD_DIR / "inbox",   # Legacy
        PRD_DIR / "rejected",# Legacy
    ]

    plans = old_state.get("plans", {})
    completed_prds = set(old_state.get("completed_prds", []))
    started_prds = set(old_state.get("started_prds", []))

    for scan_dir in prd_scan_dirs:
        if not scan_dir.exists(): continue
        
        for yaml_file in scan_dir.glob("prd_*.yaml"):
            prd_id = yaml_file.stem
            if prd_id in processed_prds:
                yaml_file.unlink() # Cleanup duplicates
                continue
            
            try:
                content = yaml_file.read_text()
                data = yaml.safe_load(content) or {}
                
                # Determine status from old state or current folder
                status = "pending"
                if prd_id in completed_prds or "done" in str(yaml_file):
                    status = "completed"
                elif prd_id in started_prds or "processing" in str(yaml_file):
                    status = "in_progress"
                elif "failed" in str(yaml_file):
                    status = "failed"

                # Enrich with old plan metadata
                if prd_id in plans:
                    plan = plans[prd_id]
                    data["TITLE"] = data.get("TITLE", plan.get("title", prd_id.replace("_", " ").title()))
                    data["DEPENDS_ON"] = data.get("DEPENDS_ON", plan.get("depends_on", []))
                    data["BRANCH"] = data.get("BRANCH", plan.get("branch", f"feature/{prd_id}"))
                    data["PARENT_BRANCH"] = data.get("PARENT_BRANCH", plan.get("parent_branch", get_main_branch()))
                else:
                    data["TITLE"] = data.get("TITLE", prd_id.replace("prd_", "").replace("_", " ").title())
                    data["BRANCH"] = data.get("BRANCH", f"feature/{prd_id}")
                    data["PARENT_BRANCH"] = data.get("PARENT_BRANCH", get_main_branch())

                # Write enriched YAML
                yaml_file.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000))

                # Move to correct destination
                target_dir = PRD_PROCESSING_DIR
                if status == "completed": target_dir = PRD_DONE_DIR
                elif status == "failed": target_dir = PRD_FAILED_DIR
                
                target_path = target_dir / yaml_file.name
                if yaml_file != target_path:
                    if not quiet: click.echo(f"  📦 Moving PRD {prd_id} to {target_dir.name}")
                    if target_path.exists(): target_path.unlink()
                    shutil.move(str(yaml_file), str(target_path))
                
                processed_prds.add(prd_id)
            except Exception as e:
                if not quiet: click.echo(f"  ⚠️  Failed to process PRD {yaml_file.name}: {e}")

    # 4. Clean up state.json
    if not quiet: click.echo("🧹 Cleaning up state files...")
    state = load_project_state()
    save_project_state(state) # This will strip redundant fields as per my new save_project_state

    # 6. Legacy folder cleanup
    legacy_prd_dirs = ["backlog", "history", "inbox", "rejected"]
    for d in legacy_prd_dirs:
        path = PRD_DIR / d
        if path.exists() and path.is_dir():
            try:
                # Only remove if empty or contains only non-PRD files we don't care about
                if not any(path.glob("prd_*.yaml")):
                    shutil.rmtree(path)
                    if not quiet: click.echo(f"  🧹 Removed legacy directory implementation/prds/{d}")
            except Exception:
                pass

    # 7. Finalize environment
    if not quiet: click.echo("🔄 Syncing environment...")
    from vibe_tools.utils import sync_env_file
    sync_env_file()

    if not quiet: click.echo("✅ Migration and reconciliation complete.")

def register_migrate(cli):
    @click.command()
    def migrate():
        """Migrate and reconcile project state with the filesystem and git."""
        run_reconciliation()

    cli.add_command(migrate)
