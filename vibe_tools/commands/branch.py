import click

from vibe_tools.branches import (
    investigate_git_lineage,
    merge_branches,
    set_branch_base,
)
from vibe_tools.utils import (
    get_automerge_branch,
    get_main_branch,
    load_config,
    load_project_state,
    run_command,
    save_config,
)


def register_branch(cli):
    @click.group(name="branch")
    @click.pass_context
    def branch_group(ctx):
        """Manage feature branches and their lineage."""
        pass

    @branch_group.command(name="base")
    @click.argument("branch_name", required=False)
    @click.argument("new_base", required=False)
    @click.pass_context
    def branch_base(ctx, branch_name, new_base):
        """Get or set the base branch for a feature branch."""
        if not branch_name:
            # Show current branch and its base
            branch_name, _ = run_command(
                ["git", "branch", "--show-current"], check=False
            )
            branch_name = branch_name.strip()

        state = load_project_state()
        lineage = state.get("branch_lineage", {})

        if new_base:
            set_branch_base(branch_name, new_base)
        else:
            current_base = lineage.get(branch_name, get_main_branch())
            click.echo(
                f"Branch {click.style(branch_name, fg='cyan')} is based on {click.style(current_base, fg='blue')}"
            )

    @branch_group.command(name="merge")
    @click.argument("src")
    @click.argument("dst")
    @click.pass_context
    def branch_merge(ctx, src, dst):
        """Merge src into dst and update lineage."""
        merge_branches(src, dst)

    @branch_group.command(name="automerge")
    @click.argument("branch_name", required=False)
    @click.pass_context
    def branch_automerge(ctx, branch_name):
        """Get or set the automerge branch."""
        config = load_config()
        if "ralph" not in config:
            config["ralph"] = {}

        if branch_name:
            main_branch = get_main_branch()
            if branch_name == main_branch:
                click.echo(
                    click.style(
                        f"❌ Automerge branch cannot be the main branch ({main_branch}).",
                        fg="red",
                    )
                )
                return

            config["ralph"]["automerge_branch"] = branch_name
            save_config(config)
            click.echo(
                f"✅ Automerge branch set to: {click.style(branch_name, fg='cyan')}"
            )

            # Verify if branch exists, if not, inform user it will be created on first use
            _, code = run_command(
                ["git", "rev-parse", "--verify", branch_name], check=False
            )
            if code != 0:
                click.echo(
                    click.style(
                        f"ℹ️ Branch '{branch_name}' does not exist yet. It will be created when needed.",
                        fg="yellow",
                    )
                )
        else:
            current_automerge = get_automerge_branch(config)
            click.echo(
                f"Current automerge branch: {click.style(current_automerge, fg='cyan')}"
            )

    @branch_group.command(name="investigate")
    @click.pass_context
    def branch_investigate(ctx):
        """Reconstruct branch lineage from git history."""
        investigate_git_lineage()

    cli.add_command(branch_group, name="branch")
