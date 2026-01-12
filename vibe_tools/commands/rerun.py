import click

from vibe_tools.utils import PRD_DIR, reset_prd_state


def register_rerun(cli):
    @click.command()
    @click.argument("prd_id")
    def rerun(prd_id):
        """Reset a PRD's state and branch to allow rerunning."""
        # Try to find the PRD file
        prd_file = None
        if prd_id.startswith("prd_") and prd_id.endswith(".yaml"):
            prd_file = PRD_DIR / prd_id
        elif prd_id.startswith("prd_"):
            prd_file = PRD_DIR / f"{prd_id}.yaml"
        else:
            # Check if it's just the number/name part
            potential_files = list(PRD_DIR.glob(f"prd_*{prd_id}*.yaml"))
            if len(potential_files) == 1:
                prd_file = potential_files[0]
            elif len(potential_files) > 1:
                click.echo(f"Multiple PRDs found matching '{prd_id}':")
                for f in potential_files:
                    click.echo(f"  - {f.name}")
                return

        if not prd_file or not prd_file.exists():
            click.echo(f"PRD '{prd_id}' not found.")
            return

        project_name = prd_file.stem
        click.echo(f"Rerunning PRD: {project_name}")

        messages = reset_prd_state(project_name)
        for msg in messages:
            click.echo(f"✅ {msg}")

        click.echo(f"\nReady to rerun: {project_name} state has been reset.")

    cli.add_command(rerun)
