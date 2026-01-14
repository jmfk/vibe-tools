import click

from vibe_tools.utils import PRODUCT_DIR, reset_prd_state


def register_rerun(cli):
    @click.command()
    @click.argument("prd_id")
    def rerun(prd_id):
        """Reset a PRD's state and branch to allow rerunning."""
        # Try to find the PRD file in product/
        prd_file = None
        
        # Search recursively for the MD file
        potential_files = list(PRODUCT_DIR.rglob(f"*{prd_id}*.md"))
        
        if len(potential_files) == 1:
            prd_file = potential_files[0]
        elif len(potential_files) > 1:
            click.echo(f"Multiple PRDs found matching '{prd_id}':")
            for f in potential_files:
                click.echo(f"  - {f.name}")
            return

        if not prd_file or not prd_file.exists():
            click.echo(f"PRD '{prd_id}' not found in {PRODUCT_DIR}.")
            return

        project_name = prd_file.stem
        # If it's a PRD-NNN-title format, project_name is the whole stem.
        # reset_prd_state handles the mapping if needed.
        click.echo(f"Rerunning PRD: {project_name}")

        messages = reset_prd_state(project_name)
        for msg in messages:
            click.echo(f"✅ {msg}")

        click.echo(f"\nReady to rerun: {project_name} state has been reset.")

    cli.add_command(rerun)
