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
        plans = state.get("plans", {})

        for info in prds:
            project_name = info["name"]
            display_name = project_name
            
            if info["has_yaml"] and info["yaml_path"]:
                prd_stem = info["yaml_path"].stem
                if prd_stem.startswith("v"):
                    display_name = prd_stem
            elif info["has_md"] and info["md_path"]:
                prd_stem = info["md_path"].stem
            else:
                prd_stem = project_name

            md_status = "✅" if info["has_md"] else "❌"
            yaml_status = "✅" if info["has_yaml"] else "❌"

            # Check status in plans first (Source of Truth)
            plan_status = None
            prd_id = f"prd_{project_name}"
            if prd_stem in plans:
                plan_status = plans[prd_stem].get("status")
            elif project_name in plans:
                plan_status = plans[project_name].get("status")
            elif prd_id in plans:
                plan_status = plans[prd_id].get("status")

            if plan_status == "completed" or prd_stem in completed_prds or project_name in completed_prds or prd_id in completed_prds:
                status = click.style("✅ DONE", fg="green")
            elif plan_status == "in_progress" or prd_stem in started_prds or project_name in started_prds or prd_id in started_prds:
                status = click.style("⏳ IN_PROGRESS", fg="blue")
            else:
                status = click.style("⚪️ PENDING", fg="white", dim=True)

            click.echo(f"{display_name:<40} {md_status:<5} {yaml_status:<5} {status:<15}")
    cli.add_command(history)
