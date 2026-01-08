import click


def register_ralph(cli):
    @click.command()
    def ralph():
        """[DEPRECATED] legacy Ralph loop. Use vibe setup/plan/implement instead."""
        click.echo(click.style("\n" + "!" * 60, fg="red", bold=True))
        click.echo(
            click.style(
                "!!! DEPRECATED: 'vibe ralph' is legacy and has been removed !!!",
                fg="red",
                bold=True,
            )
        )
        click.echo(click.style("!" * 60 + "\n", fg="red", bold=True))
        click.echo("Please use the new modular commands:")
        click.echo("  vibe architect      - Phase 1: Architecture")
        click.echo("  vibe pm             - Phase 1: PRDs")
        click.echo("  vibe normalize      - Phase 2: Standardize Specs")
        click.echo("  vibe setup          - Phase 3: Architecture Setup")
        click.echo("  vibe implement      - Phase 5: Building")
        click.echo("")

    cli.add_command(ralph)
