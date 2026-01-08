import click

from vibe_tools.setup import install_deps


def register_deps(cli):
    @click.command()
    def deps():
        """Phase 4: Install required Python and Frontend dependencies."""
        install_deps()
        click.echo("✅ Dependencies installed.")
    cli.add_command(deps)
