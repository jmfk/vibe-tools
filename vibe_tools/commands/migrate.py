import pathlib
import shutil
import json

import click

from vibe_tools.utils import (
    BACKLOG_DIR,
    HISTORY_DIR,
    PLANNING_BACKLOG_DIR,
    PLANNING_HISTORY_DIR,
    PRODUCT_DIR,
    ensure_project_structure,
    load_project_state,
    run_command,
)


def register_migrate(cli):
    @click.command()
    def migrate():
        """Migrate and reconcile project state with the filesystem and git."""
        click.echo("🚀 Starting migration and reconciliation...")

        ensure_project_structure()

        # 1. Handle project -> implementation and specs -> product migration
        from vibe_tools.utils import (
            PRODUCT_DIR,
            PRD_DIR,
            migrate_to_project_dir,
            ARCHITECTURE_SPEC,
            INFRA_SPEC,
            CICD_SPEC,
            TESTING_SPEC,
            BUILD_SPEC,
            SETUP_SPEC
        )
        migrate_to_project_dir()

        # 1.1 Move any YAML files accidentally in product/ to implementation/prds/
        if PRODUCT_DIR.exists():
            for yaml_file in PRODUCT_DIR.glob("*.yaml"):
                target_path = PRD_DIR / yaml_file.name
                if not target_path.exists():
                    click.echo(f"  📦 Moving {yaml_file.name} to implementation/prds/")
                    shutil.move(str(yaml_file), str(target_path))
                else:
                    click.echo(f"  ⚠️  {yaml_file.name} already exists in implementation/prds/, removing from product/")
                    yaml_file.unlink()

        # 1.2 Move any markdown files in implementation/ to product/
        from vibe_tools.utils import VIBE_PROJECT_DIR
        if VIBE_PROJECT_DIR.exists():
            for md_file in VIBE_PROJECT_DIR.rglob("*.md"):
                # Skip instructions if they are meant to be there, but user said NO .md in implementation
                # Actually instructions/ usually contains .txt, but let's be safe
                target_path = PRODUCT_DIR / md_file.name
                if not target_path.exists():
                    click.echo(f"  📦 Moving {md_file} to product/")
                    shutil.move(str(md_file), str(target_path))
                else:
                    click.echo(f"  ⚠️  {md_file.name} already exists in product/, removing from implementation/")
                    md_file.unlink()

        # 1.3 Ensure core lifecycle markdown files exist in product/
        core_md_files = {
            "build.md": "# Build Configuration\n\nThis file specifies the build process and configuration for the project.",
            "testing.md": "# Testing Strategy\n\nThis file defines the testing framework, targets, and requirements for the project.",
            "setup.md": "# Project Setup\n\nThis file outlines the initial setup and configuration requirements for the project.",
            "infrastructure.md": "# Infrastructure Definition\n\nThis file describes the infrastructure components and requirements.",
            "cicd.md": "# CI/CD Pipeline\n\nThis file specifies the continuous integration and deployment workflows.",
        }
        for filename, initial_content in core_md_files.items():
            file_path = PRODUCT_DIR / filename
            if not file_path.exists():
                # Only create if the corresponding YAML exists or if it's generally expected
                yaml_name = filename.replace(".md", ".yaml")
                if (PRD_DIR / yaml_name).exists() or filename in ["build.md", "testing.md"]:
                    click.echo(f"  📄 Creating missing core spec: {filename}")
                    file_path.write_text(initial_content)

        state = load_project_state()
        state_changed = False

        # 2. Reconcile PRD Files (Backlog vs History)
        click.echo("📁 Reconciling PRD file locations with state.json...")
        
        # PRD YAMLs
        completed_prds = set(state.get("completed_prds", []))
        
        # Scan filesystem for YAMLs
        found_yamls = {}
        for path in [BACKLOG_DIR, HISTORY_DIR]:
            if path.exists():
                for f in path.glob("prd_*.yaml"):
                    found_yamls[f.stem] = path

        # Sync state with filesystem
        for prd_id, path in found_yamls.items():
            is_completed = (path == HISTORY_DIR)
            
            # Update completed_prds list
            if is_completed and prd_id not in completed_prds:
                click.echo(f"  ✨ Found {prd_id} in history, marking as completed.")
                state.setdefault("completed_prds", []).append(prd_id)
                state_changed = True
            elif not is_completed and prd_id in completed_prds:
                click.echo(f"  ⚠️  {prd_id} found in backlog but marked completed in state. Moving to history.")
                target = HISTORY_DIR / f"{prd_id}.yaml"
                if not target.exists():
                    shutil.move(str(BACKLOG_DIR / f"{prd_id}.yaml"), str(target))
                else:
                    (BACKLOG_DIR / f"{prd_id}.yaml").unlink()

            # Ensure it's in state["plans"]
            if prd_id not in state.get("plans", {}):
                click.echo(f"  ➕ Adding missing PRD {prd_id} to plans.")
                state.setdefault("plans", {})[prd_id] = {
                    "status": "completed" if is_completed else "pending",
                    "file": str(path / f"{prd_id}.yaml"),
                    "title": prd_id.replace("prd_", "").replace("_", " ").title()
                }
                state_changed = True
            else:
                # Update status and file path if inconsistent
                plan = state["plans"][prd_id]
                new_status = "completed" if is_completed else plan.get("status", "pending")
                if plan.get("status") != new_status:
                    plan["status"] = new_status
                    state_changed = True
                if plan.get("file") != str(path / f"{prd_id}.yaml"):
                    plan["file"] = str(path / f"{prd_id}.yaml")
                    state_changed = True

        # 3. Check for active git branches to suggest started_prds
        click.echo("🌿 Checking for active feature branches...")
        stdout, code = run_command(["git", "branch", "--list", "feature/*"], check=False)
        if code == 0 and stdout.strip():
            started_prds = set(state.get("started_prds", []))
            for line in stdout.strip().splitlines():
                branch = line.replace("*", "").strip()
                prd_id = branch.replace("feature/", "")
                
                if prd_id in state.get("plans", {}) and state["plans"][prd_id].get("status") == "pending":
                    if prd_id not in started_prds:
                        if click.confirm(f"  💡 Found active branch '{branch}'. Mark {prd_id} as IN_PROGRESS?"):
                            state.setdefault("started_prds", []).append(prd_id)
                            state["plans"][prd_id]["status"] = "in_progress"
                            state_changed = True

        # 4. Old-style migration (cleanup)
        # Migrate from implementation/prds/ (previously project/prds/)
        old_prd_dir = pathlib.Path("implementation/prds")
        if old_prd_dir.exists() and old_prd_dir.is_dir():
            for yaml_file in old_prd_dir.glob("*.yaml"):
                # Exclude core lifecycle files - these should remain in implementation/prds/
                if yaml_file.name in ["architecture.yaml", "infrastructure.yaml", "project_overview.yaml", "cicd.yaml", "testing.yaml", "build.yaml"]:
                    continue

                prd_id = yaml_file.stem
                target_dir = HISTORY_DIR if prd_id in completed_prds else BACKLOG_DIR
                target_path = target_dir / yaml_file.name

                if not target_path.exists():
                    click.echo(f"  📦 Moving legacy {yaml_file.name} to {target_dir.name}/")
                    shutil.move(str(yaml_file), str(target_path))
                    state_changed = True
                elif yaml_file.parent == old_prd_dir:
                    yaml_file.unlink()

        # 3. Migrate from product/ (previously specs/)
        if PRODUCT_DIR.exists() and PRODUCT_DIR.is_dir():
            for md_file in PRODUCT_DIR.glob("*.md"):
                # Only move if it matches a PRD pattern or we want to organize them
                # Architecture and Infra stay in root of product/
                if md_file.name in ["architecture.md", "infrastructure.md", "cicd.md", "testing.md", "build.md", "setup.md"]:
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

        # 4. Reconcile Issue Index
        click.echo("📋 Reconciling issue index...")
        from vibe_tools.issues import load_all_issues, save_issue
        all_issues = load_all_issues()
        if all_issues:
            for issue in all_issues:
                # save_issue updates the index.json
                save_issue(issue)
            click.echo(f"  ✨ Re-indexed {len(all_issues)} issues.")

        # 5. Fix paths inside moved files
        click.echo("📝 Fixing paths inside implementation and product files...")
        _fix_content_paths()

        # 6. Cleanup legacy directories
        _cleanup_legacy_dirs()

        # 7. Finalize environment
        click.echo("🔄 Syncing environment...")
        from vibe_tools.utils import sync_env_file
        sync_env_file()

        click.echo("✅ Migration complete.")

    cli.add_command(migrate)


def _fix_content_paths():
    """Recursively fixes legacy paths inside files in implementation/ and product/."""
    replacements = [
        ("project/prds/", "implementation/prds/"),
        ("project/logs/", "implementation/logs/"),
        ("project/costs/", "implementation/costs/"),
        ("project/instructions/", "implementation/instructions/"),
        ("project/vibe_data/", "implementation/data/"),
        ("project/", "implementation/"),
        ("specs/", "product/"),
        ("prds/", "implementation/prds/"),
        ("vibe_data/", "implementation/data/"),
        ("logs/", "implementation/logs/"),
        ("costs/", "implementation/costs/"),
        ("instructions/", "implementation/instructions/"),
        ("stats/", "implementation/costs/"),
    ]

    target_dirs = [pathlib.Path("implementation"), pathlib.Path("product"), pathlib.Path("issues")]

    for target_dir in target_dirs:
        if not target_dir.exists():
            continue

        click.echo(f"  🔍 Fixing paths in {target_dir}/...")
        for file_path in target_dir.rglob("*"):
            if not file_path.is_file():
                continue

            try:
                content = file_path.read_text()
                new_content = content
                for old, new in replacements:
                    new_content = new_content.replace(old, new)

                if new_content != content:
                    click.echo(f"    ✨ Updated {file_path}")
                    file_path.write_text(new_content)
            except (UnicodeDecodeError, PermissionError):
                continue


def _cleanup_legacy_dirs():
    """Removes legacy directories if they are empty."""
    legacy_dirs = ["project", "specs", "prds", "stats", "implementation/prds/trash", "product/trash"]
    for d in legacy_dirs:
        path = pathlib.Path(d)
        if path.exists() and path.is_dir():
            # Check if empty (ignoring hidden files)
            contents = list(path.iterdir())
            if not contents:
                click.echo(f"  🧹 Removing empty legacy directory: {d}")
                try:
                    path.rmdir()
                except OSError as e:
                    click.echo(f"  ⚠️ Could not remove {d}: {e}")
            else:
                # If only contains .DS_Store or similar, remove it and the dir
                if len(contents) == 1 and contents[0].name == ".DS_Store":
                    contents[0].unlink()
                    click.echo(f"  🧹 Removing empty legacy directory (after cleaning .DS_Store): {d}")
                    try:
                        path.rmdir()
                    except OSError as e:
                        click.echo(f"  ⚠️ Could not remove {d}: {e}")
