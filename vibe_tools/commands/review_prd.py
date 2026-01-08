from typing import List

import pathlib

import click

from vibe_tools.utils import (
    SPECS_DIR,
    ensure_dir,
    get_agent_command,
    get_prompt,
    run_agent,
)


def _list_spec_files() -> List[pathlib.Path]:
    if not SPECS_DIR.exists():
        return []
    # Search recursively for markdown files
    return sorted(SPECS_DIR.rglob("*.md"))


def _prompt_for_prd(prd_paths: List[pathlib.Path]) -> pathlib.Path:
    default = len(prd_paths)
    while True:
        selection = click.prompt(
            "Select a PRD to view",
            type=int,
            default=default,
        )
        if 1 <= selection <= len(prd_paths):
            return prd_paths[selection - 1]
        click.echo("Invalid selection. Please choose a number from the list.")


def _run_agent_review(
    agent_type: str, prd_path: pathlib.Path, caffeinate: bool, stream: bool = False
) -> None:
    try:
        prompt_template = get_prompt("review_prompt.txt")
    except FileNotFoundError:
        click.echo("Review prompt template missing; skipping agentic review.")
        return

    prompt_text = prompt_template.format(prd_path=prd_path)
    command = get_agent_command(agent_type, prompt_text)
    output, exit_code = run_agent(command, caffeinate=caffeinate, stream=stream)

    if exit_code != 0:
        click.echo(f"Agentic review failed (exit {exit_code}).")
        return

    click.echo("\n--- Agentic Review Output ---")
    click.echo(output)


def register_review_prd(cli):
    @click.command(name="review-prd")
    @click.option(
        "--review/--no-review",
        type=bool,
        default=True,
        help="Run the agentic review prompt after showing the PRD.",
    )
    @click.pass_context
    def review_prd(ctx, review):
        """[DEPRECATED] List specs PRDs, display one, and optionally run review."""
        click.echo(
            click.style(
                "\n!!! DEPRECATED: 'review-prd' is deprecated !!!", fg="yellow", bold=True
            )
        )
        click.echo("'vibe prd' now includes a /review command during creation.\n")
        ensure_dir(SPECS_DIR)

        prd_files = _list_spec_files()
        if not prd_files:
            click.echo("No PRDs found in specs/.")
            return

        click.echo("Available specs:")
        for idx, prd_path in enumerate(prd_files, start=1):
            rel_path = prd_path.relative_to(SPECS_DIR)
            click.echo(f"  {idx}. {rel_path}")

        selected = _prompt_for_prd(prd_files)
        click.echo(f"\n--- {selected.name} ---")
        click.echo(selected.read_text())

        if review:
            _run_agent_review(
                agent_type=ctx.obj.get("agent", "cursor-agent"),
                prd_path=selected,
                caffeinate=ctx.obj.get("caffeinate", False),
                stream=ctx.obj.get("stream", False),
            )
