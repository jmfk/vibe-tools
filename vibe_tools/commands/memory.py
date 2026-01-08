import datetime

import click

from vibe_tools.utils import INSTRUCTIONS_DIR, ensure_dir


def register_memory(cli):
    @click.command()
    @click.argument("text", required=False)
    @click.option(
        "--list", "-l", "list_memories", is_flag=True, help="List all saved memories."
    )
    @click.option(
        "--delete", "-d", "delete_idx", type=int, help="Delete a memory by its index."
    )
    @click.option("--clear", is_flag=True, help="Clear all saved memories.")
    def memory(text, list_memories, delete_idx, clear):
        """Save a 'memory' (global instruction) that is always sent to the agent."""
        ensure_dir(INSTRUCTIONS_DIR)

        if clear:
            if click.confirm("Are you sure you want to clear all memories?", default=False):
                for f in INSTRUCTIONS_DIR.glob("*"):
                    if f.is_file():
                        f.unlink()
                click.echo("✅ All memories cleared.")
            return

        if delete_idx is not None:
            files = sorted(INSTRUCTIONS_DIR.glob("*"))
            if 1 <= delete_idx <= len(files):
                target = files[delete_idx - 1]
                if click.confirm(f"Delete memory: {target.name}?", default=True):
                    target.unlink()
                    click.echo(f"✅ Deleted {target.name}.")
            else:
                click.echo(f"❌ Invalid index: {delete_idx}")
            return

        if list_memories:
            files = sorted(INSTRUCTIONS_DIR.glob("*"))
            if not files:
                click.echo("No memories saved.")
            else:
                click.echo("Current memories:")
                for idx, f in enumerate(files, start=1):
                    content = f.read_text().strip()
                    # Show first line or truncate
                    preview = content.splitlines()[0] if content else "(empty)"
                    if len(preview) > 60:
                        preview = preview[:57] + "..."
                    click.echo(f"  {idx}. {f.name}: {preview}")
            return

        if not text:
            text = click.prompt("Enter the instruction to remember")

        if text:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            # slugify text for filename
            slug = "".join(c if c.isalnum() else "_" for c in text[:30]).lower()
            filename = f"memory_{timestamp}_{slug}.txt"
            filepath = INSTRUCTIONS_DIR / filename
            filepath.write_text(text)
            click.echo(f"✅ Memory saved to {filepath}")
