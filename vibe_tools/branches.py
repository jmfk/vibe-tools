import click
from rich.console import Console
from rich.table import Table

from vibe_tools.utils import (
    get_main_branch,
    is_merged,
    load_project_state,
    run_command,
    get_prompt,
    get_agent_command,
    run_agent,
    logger,
    is_branch_switching_enabled,
)


def display_branches_table():
    """Lists local branches and their dependencies based on project plans."""
    state = load_project_state()
    plans = state.get("plans", {})
    main_branch = get_main_branch()

    # Get local branches
    stdout, code = run_command(
        ["git", "branch", "--format=%(refname:short)"], check=False
    )
    if code != 0:
        click.echo("❌ Failed to list git branches.")
        return

    branches = stdout.splitlines()

    # Determine the next branch (first pending plan)
    next_branch = None
    for pid, pinfo in plans.items():
        if pinfo.get("status") == "pending":
            next_branch = pinfo.get("branch", f"feature/{pid}")
            break

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

        branch_display = branch
        if branch == next_branch:
            branch_display = f"[bold green]* {branch}[/bold green]"

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

            # Use parent_branch from plan if available
            parent_branch = plan_info.get("parent_branch") or branch_lineage.get(
                branch, "-"
            )

            is_merged_into_main = is_merged(branch)
            merged = "[green]✅[/green]" if is_merged_into_main else "[red]❌[/red]"

            table.add_row(
                branch_display, plan_id, status, depends_on, parent_branch, merged
            )
        else:
            # Branch exists but not tied to a known vibe plan
            table.add_row(branch_display, "-", "-", "-", parent_branch, "-")

    console.print(table)


def set_branch_base(branch: str, base: str):
    """Sets the base branch for a feature branch in state and plans."""
    state = load_project_state()

    # Update branch_lineage
    if "branch_lineage" not in state:
        state["branch_lineage"] = {}
    state["branch_lineage"][branch] = base

    # Update corresponding plan if it exists
    plan_id = None
    if branch.startswith("feature/"):
        plan_id = branch.replace("feature/", "")

    if plan_id and plan_id in state.get("plans", {}):
        state["plans"][plan_id]["parent_branch"] = base
    elif branch in state.get("plans", {}):
        state["plans"][branch]["parent_branch"] = base

    from vibe_tools.utils import save_project_state

    save_project_state(state)
    click.echo(
        f"✅ Set base for {click.style(branch, fg='cyan')} to {click.style(base, fg='blue')}"
    )


def merge_branches(src: str, dst: str):
    """Merges src branch into dst branch and updates lineage."""
    from vibe_tools.utils import (
        get_main_branch,
        load_project_state,
        run_command,
        save_project_state,
        is_branch_switching_enabled,
    )

    if not is_branch_switching_enabled():
        click.echo(
            f"⚠️ Branch switching is disabled. Merge from {src} to {dst} might fail if not on the correct branch."
        )

    click.echo(
        f"🔄 Merging {click.style(src, fg='cyan')} into {click.style(dst, fg='cyan')}..."
    )

    # 1. Ensure dst exists, if not create it from main
    _, code = run_command(["git", "rev-parse", "--verify", dst], check=False)
    if code != 0:
        main_branch = get_main_branch()
        click.echo(
            f"🌿 Destination branch {click.style(dst, fg='cyan')} does not exist. Creating from {click.style(main_branch, fg='blue')}..."
        )
        run_command(["git", "checkout", main_branch], check=False)
        run_command(["git", "checkout", "-b", dst], check=False)
        # Switch back to src to perform the merge from the right context if needed,
        # though git merge can be done from dst.

    # 2. Checkout dst
    _, code = run_command(["git", "checkout", dst], check=False)
    if code != 0:
        click.echo(f"❌ Failed to checkout {dst}")
        return

    # 3. Merge src
    stdout, code = run_command(["git", "merge", src], check=False)
    if code != 0:
        click.echo(f"❌ Merge failed:\n{stdout}")
        return

    # 3. Update state - dst now depends on or is based on src's parent or similar
    # In this case, the user explicitly merged, so we record dst's parent as src
    state = load_project_state()
    if "branch_lineage" not in state:
        state["branch_lineage"] = {}
    state["branch_lineage"][dst] = src

    # Update plan if exists
    plan_id = None
    if dst.startswith("feature/"):
        plan_id = dst.replace("feature/", "")

    if plan_id and plan_id in state.get("plans", {}):
        state["plans"][plan_id]["parent_branch"] = src
    elif dst in state.get("plans", {}):
        state["plans"][dst]["parent_branch"] = src

    save_project_state(state)
    click.echo(f"✅ Successfully merged and updated lineage: {dst} -> {src}")


def investigate_git_lineage():
    """Heuristically reconstruct branch lineage from git history."""
    from vibe_tools.utils import (
        get_main_branch,
        load_project_state,
        run_command,
        save_project_state,
    )

    click.echo("🔍 Investigating git history to reconstruct lineage...")

    stdout, code = run_command(
        ["git", "branch", "--format=%(refname:short)"], check=False
    )
    if code != 0:
        return

    branches = stdout.splitlines()
    main_branch = get_main_branch()
    state = load_project_state()
    if "branch_lineage" not in state:
        state["branch_lineage"] = {}

    for branch in branches:
        if branch == main_branch:
            continue

        # Find the merge base with all other branches to find the closest parent
        best_parent = main_branch
        best_base_date = 0

        for other in branches:
            if other == branch:
                continue

            # Get the merge base
            base_sha, code = run_command(
                ["git", "merge-base", branch, other], check=False
            )
            if code == 0 and base_sha:
                # Get the date of the merge base commit
                date_str, _ = run_command(
                    ["git", "show", "-s", "--format=%ct", base_sha], check=False
                )
                if date_str:
                    date_val = int(date_str)
                    if date_val > best_base_date:
                        best_base_date = date_val
                        best_parent = other

        state["branch_lineage"][branch] = best_parent

        # Sync with plans
        plan_id = None
        if branch.startswith("feature/"):
            plan_id = branch.replace("feature/", "")

        if plan_id and plan_id in state.get("plans", {}):
            state["plans"][plan_id]["parent_branch"] = best_parent
        elif branch in state.get("plans", {}):
            state["plans"][branch]["parent_branch"] = best_parent

    save_project_state(state)
    click.echo("✅ Reconstructed branch lineage from history.")


def _switch_to_branch(
    branch_name, agent, project_name, parent_branch=None, stream=False
):
    """Robustly switches to a feature branch, using AI rescue if needed."""
    if not is_branch_switching_enabled():
        logger.info(
            f"Branch switching is disabled. Staying on current branch instead of switching to '{branch_name}'."
        )
        return

    import sys
    from vibe_tools import utils

    if parent_branch is None:
        parent_branch = get_main_branch()

    # Check if we are already on this branch
    stdout, _ = run_command(["git", "branch", "--show-current"], check=False)
    if stdout.strip() == branch_name:
        return

    # Check if branch exists in git
    _, code = run_command(["git", "rev-parse", "--verify", branch_name], check=False)
    branch_exists = code == 0

    if branch_exists:
        logger.info(f"Branch '{branch_name}' already exists. Switching...")
        output, code = run_command(["git", "checkout", branch_name], check=False)
    else:
        logger.info(
            f"Creating and switching to branch: {branch_name} from {parent_branch}"
        )
        # Ensure parent branch exists locally or pull it
        run_command(["git", "checkout", parent_branch], check=False)
        output, code = run_command(["git", "checkout", "-b", branch_name], check=False)

    if code != 0:
        logger.warning(
            f"Git operation failed for branch '{branch_name}': {output}. Calling agent to sort it out..."
        )
        git_status, _ = run_command(["git", "status"], check=False)
        try:
            prompt_template = get_prompt("git_fix_prompt.txt")
        except FileNotFoundError as e:
            logger.error(f"Error: {e}")
            sys.exit(1)

        prompt = prompt_template.format(
            branch_name=branch_name,
            project_name=project_name,
            error=output,
            git_status=git_status,
        )
        cmd = get_agent_command(agent, prompt)

        if utils.verbose_logger:
            utils.verbose_logger.log_event("prompt", prompt, f"{project_name}_git_fix")

        output, _ = run_agent(cmd, stream=stream)

        if utils.verbose_logger:
            utils.verbose_logger.log_event("reply", output, f"{project_name}_git_fix")

        # Final attempt after agent fix
        final_output, final_code = run_command(
            ["git", "checkout", branch_name], check=False
        )
        if final_code != 0:
            logger.error(
                f"Agent was unable to resolve git conflict. Final error: {final_output}"
            )
            sys.exit(1)
