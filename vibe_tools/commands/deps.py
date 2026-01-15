import click

from vibe_tools.setup import install_deps


def register_deps(cli):
    @click.command()
    @click.option(
        "--makefile",
        "only_makefile",
        is_flag=True,
        help="Only synchronize the Makefile.",
    )
    @click.option(
        "--python",
        "only_python",
        is_flag=True,
        help="Only install Python dependencies.",
    )
    @click.option(
        "--frontend",
        "only_frontend",
        is_flag=True,
        help="Only install Frontend dependencies.",
    )
    def deps(only_makefile, only_python, only_frontend):
        """Phase 2: Install required Python and Frontend dependencies."""
        install_deps(
            only_makefile=only_makefile,
            only_python=only_python,
            only_frontend=only_frontend,
        )
        click.echo("✅ Dependencies process completed.")

    cli.add_command(deps)
