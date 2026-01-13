import click
import pathlib
import shutil
import re
from typing import Optional, List

from vibe_tools.utils import (
    collect_all_prd_info,
    load_project_state,
    reset_prd_state,
    PRODUCT_BACKLOG_DIR,
    PRODUCT_IN_PROGRESS_DIR,
    PRODUCT_HISTORY_DIR,
    PLANNING_INBOX_DIR,
    PLANNING_REJECTED_DIR,
    ensure_dir,
    logger,
    save_project_state
)
from vibe_tools.pm import InteractivePM
from vibe_tools.prds import load_prd, PRD


def register_prd(cli):
    @click.group(invoke_without_command=True)
    @click.pass_context
    def prd(ctx):
        """Manage PRDs and initiatives."""
        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    @prd.command(name="list")
    @click.option("--all", is_flag=True, help="Show all PRDs including history.")
    def list_prds(all):
        """List unified PRDs and their status."""
        state = load_project_state()
        
        # Collect PRDs from new structure
        backlog = sorted(list(PRODUCT_BACKLOG_DIR.glob("*.md")))
        in_progress = list(PRODUCT_IN_PROGRESS_DIR.glob("*.md"))
        history = sorted(list(PRODUCT_HISTORY_DIR.glob("*.md")), reverse=True)
        
        click.echo(f"{'ID':<10} {'Type':<10} {'Status':<15} {'Group':<15} {'Title'}")
        click.echo("-" * 80)
        
        def print_prd(path: pathlib.Path):
            try:
                p = load_prd(path)
                status_color = "white"
                if p.status == "done": status_color = "green"
                elif p.status == "in_progress": status_color = "blue"
                
                status_str = click.style(p.status.upper(), fg=status_color)
                type_str = click.style(p.type, fg="cyan" if p.type == "FEATURE" else "yellow")
                group_str = p.group or "-"
                click.echo(f"{p.id:<10} {type_str:<10} {status_str:<15} {group_str:<15} {p.title}")
            except Exception:
                click.echo(f"{path.name:<10} {'ERROR':<10} {'-':<15} {'-':<15} {path.name}")

        for f in in_progress: print_prd(f)
        for f in backlog: print_prd(f)
        if all:
            for f in history: print_prd(f)
        elif history:
            click.echo(click.style(f"... and {len(history)} items in history (use --all to see them)", dim=True))

    @prd.command(name="plan")
    def plan_prds():
        """Interactively prioritize the product backlog."""
        backlog = sorted(list(PRODUCT_BACKLOG_DIR.glob("*.md")))
        if not backlog:
            click.echo("No PRDs in backlog.")
            return

        click.echo("\n--- Product Backlog ---")
        for i, f in enumerate(backlog, 1):
            try:
                p = load_prd(f)
                click.echo(f"{i}. [{p.id}] {p.title}")
            except Exception:
                click.echo(f"{i}. {f.name}")

        click.echo("\nOptions: [q]uit, [m]ove <idx> to top, [s]tart <idx>")
        choice = click.prompt("Selection", type=str, default="q")
        
        if choice.startswith("m "):
            try:
                idx = int(choice.split()[1]) - 1
                if 0 <= idx < len(backlog):
                    selected = backlog[idx]
                    # Simple way to move to top in sorted list: rename with prefix
                    # But we want to avoid prefixing if possible.
                    # For now let's just use a hidden priority in frontmatter.
                    p = load_prd(selected)
                    p.metadata["priority"] = 0 # Future use
                    # For now, we'll just rename the file to something that sorts first
                    new_name = f"000-{selected.name}"
                    selected.rename(PRODUCT_BACKLOG_DIR / new_name)
                    click.echo(f"Moved {p.id} to top.")
            except (ValueError, IndexError):
                click.echo("Invalid index.")
        elif choice.startswith("s "):
            try:
                idx = int(choice.split()[1]) - 1
                if 0 <= idx < len(backlog):
                    # Check if anything else is in progress
                    if list(PRODUCT_IN_PROGRESS_DIR.glob("*.md")):
                        click.echo("❌ Another PRD is already in progress.")
                        return
                    
                    selected = backlog[idx]
                    p = load_prd(selected)
                    p.status = "in_progress"
                    new_path = PRODUCT_IN_PROGRESS_DIR / selected.name
                    p.save(new_path)
                    selected.unlink()
                    click.echo(f"Started {p.id}. Run 'vibe implement' to begin.")
            except (ValueError, IndexError):
                click.echo("Invalid index.")

    @prd.command(name="pm")
    @click.argument("query", required=False)
    @click.pass_context
    def pm_command(ctx, query):
        """Phase 1: Interactive PRD and specification manager."""
        pm_tool = InteractivePM(
            agent_type=ctx.obj.get("agent", "cursor-agent"),
            stream=ctx.obj.get("stream", True),
        )
        pm_tool.run(query)

    @prd.command(name="move")
    @click.argument("prd_id")
    @click.argument("target", type=click.Choice(["backlog", "history", "rejected"]))
    def move_prd(prd_id, target):
        """Move a PRD by its ID."""
        # Find the file
        all_files = list(PRODUCT_DIR.rglob("*.md"))
        found_path = None
        for f in all_files:
            if prd_id.upper() in f.name:
                found_path = f
                break
        
        if not found_path:
            click.echo(f"❌ PRD not found: {prd_id}")
            return
            
        target_map = {
            "backlog": PRODUCT_BACKLOG_DIR,
            "history": PRODUCT_HISTORY_DIR,
            "rejected": PLANNING_REJECTED_DIR,
        }
        
        target_dir = target_map[target]
        ensure_dir(target_dir)
        
        p = load_prd(found_path)
        p.status = "done" if target == "history" else "backlog"
        new_path = target_dir / found_path.name
        p.save(new_path)
        found_path.unlink()
        
        click.echo(f"✅ Moved {prd_id} to {target}")

    cli.add_command(prd)
