import click


def register_remember(cli):
    @click.command()
    @click.argument("text", required=False)
    @click.option(
        "--list", "-l", "list_memories", is_flag=True, help="List all saved memories."
    )
    @click.option(
        "--delete", "-d", "delete_idx", type=int, help="Delete a memory by its index."
    )
    @click.option("--clear", is_flag=True, help="Clear all saved memories.")
    @click.pass_context
    def remember(ctx, text, list_memories, delete_idx, clear):
        """Alias for 'vibe memory'."""
        from vibe_tools.commands.memory import memory
        ctx.invoke(
            memory,
            text=text,
            list_memories=list_memories,
            delete_idx=delete_idx,
            clear=clear,
        )
