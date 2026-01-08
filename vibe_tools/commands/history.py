import click

from vibe_tools.utils import collect_all_prd_info, load_project_state


def register_history(cli):
    @click.command()
    def history():
        """List the status of all PRDs."""
        prds = collect_all_prd_info()
        if not prds:
            click.echo("No PRD files found.")
            return

        click.echo(f"{'PRD':<40} {'MD':<5} {'YAML':<5} {'Status':<15}")
        click.echo("-" * 70)

        state = load_project_state()
        completed_prds = state.get("completed_prds", [])
        started_prds = state.get("started_prds", [])

        for info in prds:
            project_name = info["name"]

            # We need the actual stem used in state.json (which is usually prd_name or the yaml stem)
            # The project state stores names like '01_pm_prd_focus' or 'prd_01_pm_prd_focus'
            # Let's check both the clean name and the prd_ prefixed name
            prd_stem = project_name
            if info["has_yaml"] and info["yaml_path"]:
                prd_stem = info["yaml_path"].stem
            elif info["has_md"] and info["md_path"]:
                # If only MD exists, it's definitely pending/started by its stem or clean name
                prd_stem = info["md_path"].stem

            md_status = "✅" if info["has_md"] else "❌"
            yaml_status = "✅" if info["has_yaml"] else "❌"

            if prd_stem in completed_prds or project_name in completed_prds:
                status = click.style("✅ DONE", fg="green")
            elif prd_stem in started_prds or project_name in started_prds:
                status = click.style("⏳ IN_PROGRESS", fg="blue")
            else:
                status = click.style("⚪️ PENDING", fg="white", dim=True)

            click.echo(f"{project_name:<40} {md_status:<5} {yaml_status:<5} {status:<15}")
    cli.add_command(history)
