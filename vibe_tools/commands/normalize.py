import click
import pathlib
from vibe_tools.normalize import normalize_prd


def register_normalize(cli):
    @click.command()
    @click.argument(
        "input_file",
        type=click.Path(exists=True, path_type=pathlib.Path),
        required=False,
    )
    @click.option(
        "--auto-overwrite",
        "--yes",
        "-y",
        is_flag=True,
        help="Automatically overwrite existing YAML files.",
    )
    @click.pass_context
    def normalize(ctx, input_file, auto_overwrite):
        """Phase 1: Normalize high-level PRDs into machine-readable plans."""
        normalize_prd(
            input_file=input_file,
            auto_overwrite=auto_overwrite,
            debug=ctx.obj.get("debug", False),
        )

    cli.add_command(normalize)
