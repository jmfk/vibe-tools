import click
from rich.console import Console
from rich.table import Table
from vibe_tools.utils import (
    load_project_state,
    run_command,
    get_main_branch,
    is_merged,
)

def display_branches_table():
    """Lists local branches and their dependencies based on project plans."""
    state = load_project_state()
    plans = state.get("plans", {})
    main_branch = get_main_branch()
    
    # Get local branches
    stdout, code = run_command(["git", "branch", "--format=%(refname:short)"], check=False)
    if code != 0:
        click.echo("❌ Failed to list git branches.")
        return
    
    branches = stdout.splitlines()
    
    console = Console()
    table = Table(title="Vibe Project Branches")
    table.add_column("Branch", style="cyan")
    table.add_column("Plan ID", style="magenta")
    table.add_column("Status", style="bold")
    table.add_column("Depends On", style="yellow")
    table.add_column("Parent Branch", style="blue")
    table.add_column("Merged", justify="center")

    branch_lineage = state.get("branch_lineage", {})

    for branch in branches:
        plan_id = None
        status = "-"
        depends_on = "-"
        parent_branch = branch_lineage.get(branch, "-")
        merged = "-"

        if branch == main_branch:
            table.add_row(f"[bold]{branch}[/bold]", "-", "-", "-", "-", "-")
            continue

        # Try to match branch to plan ID
        # Branches are usually feature/plan_id
        if branch.startswith("feature/"):
            potential_plan_id = branch.replace("feature/", "")
            if potential_plan_id in plans:
                plan_id = potential_plan_id
        
        # Fallback: check if branch name itself is a plan ID
        if not plan_id and branch in plans:
            plan_id = branch

        if plan_id:
            plan_info = plans[plan_id]
            status_val = plan_info.get("status", "pending")
            if status_val == "completed":
                status = "[green]DONE[/green]"
            elif status_val == "in_progress":
                status = "[blue]IN_PROGRESS[/blue]"
            else:
                status = "[white]PENDING[/white]"
            
            deps = plan_info.get("depends_on", [])
            depends_on = ", ".join(deps) if deps else "-"
            
            is_merged_into_main = is_merged(branch)
            merged = "[green]✅[/green]" if is_merged_into_main else "[red]❌[/red]"
            
            table.add_row(branch, plan_id, status, depends_on, parent_branch, merged)
        else:
            # Branch exists but not tied to a known vibe plan
            table.add_row(branch, "-", "-", "-", parent_branch, "-")

    console.print(table)

