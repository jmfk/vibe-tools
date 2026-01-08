import pathlib

import click

from vibe_tools.utils import ensure_dir


def register_prd(cli):
    @click.command()
    @click.option(
        "--title",
        "-t",
        help="Short description of the PRD or feature you want to explore.",
    )
    @click.option(
        "--type",
        "-T",
        type=click.Choice(["feature", "infra", "cicd", "architecture"]),
        default="feature",
        help="Type of PRD to write (default: feature).",
    )
    @click.pass_context
    def prd(ctx, title, type):
        """[DEPRECATED] Use 'vibe pm' instead. Interactive PRD writer with slash commands."""
        click.echo(
            click.style("\n!!! DEPRECATED: 'prd' is deprecated !!!", fg="yellow", bold=True)
        )
        click.echo("Please use 'vibe pm' for the newer interactive experience.\n")
        from vibe_tools.prd_writer import InteractivePRD

        initial_prompt = title or click.prompt(
            f"Describe the {type} PRD you'd like to write"
        )

        # Base specs dir
        specs_base = pathlib.Path("specs")
        ensure_dir(specs_base)

        writer = InteractivePRD(
            agent_type=ctx.obj.get("agent", "cursor-agent"),
            specs_dir=specs_base,
            prd_type=type,
            stream=ctx.obj.get("stream", False),
        )
        writer.run_loop(initial_prompt)
