import json

import click

from vibe_tools.utils import (
    get_agent_command,
    get_prompt,
    load_project_state,
    run_agent,
    run_command,
)


def register_branch_resolve(cli):
    @click.command(name="branch-resolve")
    @click.pass_context
    def branch_resolve(ctx):
        """Use the agent to resolve git history/conflicts across the branch stack."""
        agent = ctx.obj.get("agent", "cursor-agent")
        stream = ctx.obj.get("stream", False)

        click.echo("🔍 Analyzing git history and branch lineage...")

        git_status, _ = run_command(["git", "status"], check=False)
        git_log, _ = run_command(
            ["git", "log", "--oneline", "--graph", "--all", "-n", "20"], check=False
        )
        git_branches, _ = run_command(["git", "branch", "-a"], check=False)

        state = load_project_state()
        lineage = json.dumps(state.get("branch_lineage", {}), indent=2)

        try:
            prompt_template = get_prompt("git_resolve_prompt.txt")
        except FileNotFoundError:
            click.echo("❌ Prompt template 'git_resolve_prompt.txt' not found.")
            return

        prompt = prompt_template.format(
            git_status=git_status,
            git_log=git_log,
            git_branches=git_branches,
            lineage=lineage,
        )

        click.echo(f"🤖 Calling {agent} to resolve git state...")
        cmd = get_agent_command(agent, prompt)
        output, code = run_agent(cmd, stream=stream)

        if code == 0:
            click.echo("✅ Git resolution attempt completed.")
        else:
            click.echo(f"❌ Git resolution failed (exit code {code}).")

    cli.add_command(branch_resolve)
