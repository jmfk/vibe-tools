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
    PRODUCT_DIR,
    PLANNING_INBOX_DIR,
    PLANNING_REJECTED_DIR,
    ensure_dir,
    logger,
    save_project_state
)
from vibe_tools.pm import InteractivePM
from vibe_tools.prds import load_prd, PRD


def _get_all_prds() -> List[PRD]:
    all_files = list(PRODUCT_DIR.rglob("*.md"))
    prds = []
    for f in all_files:
        try:
            prds.append(load_prd(f))
        except Exception:
            continue
    return prds


def _check_and_suggest_dependencies(prd: PRD, all_prds: List[PRD], completed: List[str]):
    missing = [d for d in prd.depends_on if d not in completed]
    if not missing:
        return True

    click.echo(
        click.style(f"\n⚠️  PRD {prd.id} depends on: {', '.join(missing)}", fg="yellow")
    )

    for dep_id in missing:
        dep_prd = next((p for p in all_prds if p.id == dep_id), None)
        if not dep_prd:
            click.echo(f"❌ Dependency {dep_id} not found in any PRD files.")
            continue

        # Check where it is
        status = dep_prd.status
        path = dep_prd.path

        if status == "done":
            # Should already be in completed, but double check
            continue
        elif status == "in_progress":
            click.echo(f"ℹ️  {dep_id} is already IN PROGRESS.")
        elif status in ["backlog", "inbox"]:
            if click.confirm(
                f"👉 {dep_id} is in {status.upper()}. Would you like to start it first?"
            ):
                # Recursively check its dependencies
                if _check_and_suggest_dependencies(dep_prd, all_prds, completed):
                    # Start this dependency
                    # Check if anything else is in progress
                    in_progress = list(PRODUCT_IN_PROGRESS_DIR.glob("*.md"))
                    if in_progress:
                        for f in in_progress:
                            p_to_stop = load_prd(f)
                            p_to_stop.status = "backlog"
                            p_to_stop.save(PRODUCT_BACKLOG_DIR / f.name)
                            f.unlink()

                    dep_prd.status = "in_progress"
                    new_path = PRODUCT_IN_PROGRESS_DIR / dep_prd.path.name
                    dep_prd.save(new_path)
                    dep_prd.path.unlink()
                    click.echo(f"✅ Started {dep_id}. Run 'vibe implement' to begin.")
                    return False  # We started a dependency instead
        else:
            click.echo(
                f"⚠️  {dep_id} has status '{status}' at {path}. Please resolve this dependency manually."
            )

    return True


def _print_prd_line(path: pathlib.Path):
    try:
        p = load_prd(path)
        status_color = "white"
        if p.status == "done":
            status_color = "green"
        elif p.status == "in_progress":
            status_color = "blue"

        status_str = click.style(p.status.upper(), fg=status_color)
        type_str = click.style(
            p.type, fg="cyan" if p.type == "FEATURE" else "yellow"
        )
        group_str = p.group or "-"
        click.echo(
            f"{p.id:<10} {type_str:<10} {status_str:<15} {group_str:<15} {p.title}"
        )
    except Exception:
        click.echo(f"{path.name:<10} {'ERROR':<10} {'-':<15} {'-':<15} {path.name}")


def _display_prd_list(files: List[pathlib.Path], title: Optional[str] = None):
    if title:
        click.echo(click.style(f"\n--- {title} ---", bold=True))

    click.echo(f"{'ID':<10} {'Type':<10} {'Status':<15} {'Group':<15} {'Title'}")
    click.echo("-" * 80)

    if not files:
        click.echo(click.style("No PRDs found.", dim=True))
        return

    for f in files:
        _print_prd_line(f)


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

        if in_progress:
            _display_prd_list(in_progress, "In Progress")
        
        if backlog:
            _display_prd_list(backlog, "Backlog")

        if all:
            if history:
                _display_prd_list(history, "History")
        elif history:
            click.echo(
                click.style(
                    f"\n... and {len(history)} items in history (use --all or 'vibe prd history' to see them)",
                    dim=True,
                )
            )

    @prd.command(name="history")
    def prd_history():
        """List PRD history."""
        history = sorted(list(PRODUCT_HISTORY_DIR.glob("*.md")), reverse=True)
        _display_prd_list(history, "PRD History")

    @prd.command(name="rejected")
    def prd_rejected():
        """List rejected PRDs."""
        rejected = sorted(list(PLANNING_REJECTED_DIR.glob("*.md")), reverse=True)
        _display_prd_list(rejected, "Rejected PRDs")

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
                deps_str = f" (deps: {', '.join(p.depends_on)})" if p.depends_on else ""
                click.echo(f"{i}. [{p.id}] {p.title}{deps_str}")
            except Exception:
                click.echo(f"{i}. {f.name}")

    click.echo("\nOptions: [q]uit, [m]ove <idx> to top, [s]tart <idx>, [a]dd dep <idx> <dep_id>")
    choice = click.prompt("Selection", type=str, default="q")

    if choice.startswith("m "):
        try:
            idx = int(choice.split()[1]) - 1
            if 0 <= idx < len(backlog):
                selected = backlog[idx]
                p = load_prd(selected)
                p.metadata["priority"] = 0
                new_name = f"000-{selected.name}"
                selected.rename(PRODUCT_BACKLOG_DIR / new_name)
                click.echo(f"Moved {p.id} to top.")
        except (ValueError, IndexError):
            click.echo("Invalid index.")
    elif choice.startswith("a "):
        try:
            parts = choice.split()
            if len(parts) < 4:
                click.echo("Usage: a dep <idx> <dep_id>")
                return
            idx = int(parts[2]) - 1
            dep_id = parts[3].upper()
            if 0 <= idx < len(backlog):
                selected_file = backlog[idx]
                p = load_prd(selected_file)
                if dep_id not in p.depends_on:
                    p.depends_on.append(dep_id)
                    p.save()
                    click.echo(f"✅ Added dependency {dep_id} to {p.id}")
                else:
                    click.echo(f"ℹ️  {p.id} already depends on {dep_id}")
        except (ValueError, IndexError):
            click.echo("Invalid index.")
    elif choice.startswith("s "):
            try:
                idx = int(choice.split()[1]) - 1
                if 0 <= idx < len(backlog):
                    selected_file = backlog[idx]
                    p = load_prd(selected_file)
                    
                    # Check dependencies
                    state = load_project_state()
                    completed = state.get("completed_prds", [])
                    all_prds = _get_all_prds()
                    
                    if not _check_and_suggest_dependencies(p, all_prds, completed):
                        return

                    # Check if anything else is in progress
                    in_progress = list(PRODUCT_IN_PROGRESS_DIR.glob("*.md"))
                    if in_progress:
                        curr_p = load_prd(in_progress[0])
                        if click.confirm(
                            f"⚠️  PRD {curr_p.id} is already in progress. Move it back to backlog?"
                        ):
                            for f in in_progress:
                                p_to_stop = load_prd(f)
                                p_to_stop.status = "backlog"
                                p_to_stop.save(PRODUCT_BACKLOG_DIR / f.name)
                                f.unlink()
                        else:
                            click.echo("Aborted.")
                            return

                    p.status = "in_progress"
                    new_path = PRODUCT_IN_PROGRESS_DIR / selected_file.name
                    p.save(new_path)
                    selected_file.unlink()
                    click.echo(f"Started {p.id}. Run 'vibe implement' to begin.")
            except (ValueError, IndexError):
                click.echo("Invalid index.")

    @prd.command(name="stop")    def stop_prd():
        """Move the current in-progress PRD back to the backlog."""
        in_progress = list(PRODUCT_IN_PROGRESS_DIR.glob("*.md"))
        if not in_progress:
            click.echo("No PRD is currently in progress.")
            return

        for f in in_progress:
            p = load_prd(f)
            p.status = "backlog"
            new_path = PRODUCT_BACKLOG_DIR / f.name
            p.save(new_path)
            f.unlink()
            click.echo(f"✅ Stopped {p.id} and moved back to backlog.")

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
    @click.argument(
        "target", type=click.Choice(["backlog", "history", "rejected", "in_progress"])
    )
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
            "in_progress": PRODUCT_IN_PROGRESS_DIR,
        }

        if target == "in_progress":
            existing = list(PRODUCT_IN_PROGRESS_DIR.glob("*.md"))
            if existing and existing[0].name != found_path.name:
                click.echo("❌ Another PRD is already in progress.")
                return

        target_dir = target_map[target]
        ensure_dir(target_dir)

        p = load_prd(found_path)
        if target == "history":
            p.status = "done"
        elif target == "in_progress":
            p.status = "in_progress"
        else:
            p.status = "backlog"

        new_path = target_dir / found_path.name
        p.save(new_path)
        found_path.unlink()

        click.echo(f"✅ Moved {prd_id} to {target}")

    cli.add_command(prd)
