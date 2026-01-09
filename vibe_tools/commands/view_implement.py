import pathlib
import click
from vibe_tools.utils import (
    INBOX_DIR,
    BACKLOG_DIR,
    HISTORY_DIR,
    TRASH_DIR,
    PRD_DIR,
    open_in_editor,
    logger,
)

def list_prds(directory: pathlib.Path, search_term: str = None, page: int = 1):
    """Helper to list PRDs in a directory with paging and search."""
    if not directory.exists():
        click.echo(f"Directory {directory} does not exist.")
        return

    files = sorted(list(directory.glob("*.yaml")) + list(directory.glob("*.md")))
    if search_term:
        files = [f for f in files if search_term.lower() in f.name.lower()]

    batch_size = 10
    total_pages = (len(files) + batch_size - 1) // batch_size if files else 1
    
    start_idx = (page - 1) * batch_size
    end_idx = start_idx + batch_size
    batch = files[start_idx:end_idx]

    click.echo(click.style(f"\n--- PRDs in {directory.name} (Page {page}/{total_pages}) ---", fg="cyan", bold=True))
    if not batch:
        click.echo("  No PRDs found.")
        return

    for i, f in enumerate(batch, 1):
        click.echo(f"  {start_idx + i}. {f.name}")
    
    if total_pages > 1:
        click.echo(f"\nUse '--page' to see other pages (Total items: {len(files)})")

def find_prd(prd_id: str):
    """Finds a PRD file by ID or partial name across all PRD folders."""
    for folder in [INBOX_DIR, BACKLOG_DIR, HISTORY_DIR, TRASH_DIR]:
        # Try exact match first
        exact = folder / prd_id
        if exact.exists():
            return exact
        
        # Try with extensions
        for ext in [".yaml", ".md"]:
            f = folder / f"{prd_id}{ext}"
            if f.exists():
                return f
        
        # Try partial match
        matches = list(folder.glob(f"*{prd_id}*"))
        if matches:
            return matches[0]
    return None

@click.group(invoke_without_command=True)
@click.option("--search", "-s", help="Search term to filter PRDs.")
@click.option("--page", "-p", default=1, help="Page number.")
@click.pass_context
def i(ctx, search, page):
    """View and manage PRD implementation workflow."""
    if ctx.invoked_subcommand is None:
        # Default to listing backlog
        list_prds(BACKLOG_DIR, search, page)

@i.command()
@click.option("--search", "-s", help="Search term to filter PRDs.")
@click.option("--page", "-p", default=1, help="Page number.")
def inbox(search, page):
    """List PRDs in the inbox."""
    list_prds(INBOX_DIR, search, page)

@i.command()
@click.option("--search", "-s", help="Search term to filter PRDs.")
@click.option("--page", "-p", default=1, help="Page number.")
def backlog(search, page):
    """List PRDs in the backlog."""
    list_prds(BACKLOG_DIR, search, page)

@i.command()
@click.option("--search", "-s", help="Search term to filter PRDs.")
@click.option("--page", "-p", default=1, help="Page number.")
def history(search, page):
    """List implemented PRDs in history."""
    list_prds(HISTORY_DIR, search, page)

@i.command()
@click.option("--search", "-s", help="Search term to filter PRDs.")
@click.option("--page", "-p", default=1, help="Page number.")
def trash(search, page):
    """List dismissed PRDs in trash."""
    list_prds(TRASH_DIR, search, page)

@i.command()
@click.option("--search", "-s", help="Search term to filter PRDs.")
def all(search):
    """List all PRDs across all folders."""
    for folder in [INBOX_DIR, BACKLOG_DIR, HISTORY_DIR, TRASH_DIR]:
        list_prds(folder, search)

@i.command()
@click.argument("prd_id")
@click.argument("target", type=click.Choice(["inbox", "backlog", "history", "trash"]))
def move(prd_id, target):
    """Move a PRD to a different status folder."""
    target_map = {
        "inbox": INBOX_DIR,
        "backlog": BACKLOG_DIR,
        "history": HISTORY_DIR,
        "trash": TRASH_DIR,
    }
    
    source_file = find_prd(prd_id)
    if not source_file:
        click.echo(f"❌ Could not find PRD: {prd_id}")
        return

    target_dir = target_map[target]
    target_path = target_dir / source_file.name

    if source_file.parent == target_dir:
        click.echo(f"ℹ️ PRD is already in {target}")
        return

    import shutil
    shutil.move(str(source_file), str(target_path))
    click.echo(f"✅ Moved {source_file.name} to {target}")

@i.command()
@click.argument("prd_id")
def dismiss(prd_id):
    """Move a PRD to the trash folder."""
    source_file = find_prd(prd_id)
    if not source_file:
        click.echo(f"❌ Could not find PRD: {prd_id}")
        return

    target_path = TRASH_DIR / source_file.name
    import shutil
    shutil.move(str(source_file), str(target_path))
    click.echo(f"✅ Dismissed {source_file.name} to trash")

@i.command()
@click.argument("prd_id")
def edit(prd_id):
    """Open a PRD in the configured editor."""
    source_file = find_prd(prd_id)
    if not source_file:
        click.echo(f"❌ Could not find PRD: {prd_id}")
        return
    
    open_in_editor(source_file)

def register_view_implement(cli):
    cli.add_command(i)
    # Also register as 'view implement' if needed, but 'i' is the requested short form.
    # To support 'view implement', we'd need a 'view' group.
    
    @click.group()
    def view():
        """View project components."""
        pass
    
    view.add_command(i, name="implement")
    cli.add_command(view)
