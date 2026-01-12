import click

from vibe_tools.fixer import run_test_fix_loop


def register_test_fix(cli):
    @click.command()
    @click.option(
        "--fast/--no-fast",
        is_flag=True,
        default=False,
        help="Only run tests for changed files (more efficient).",
    )
    @click.pass_context
    def test_fix(ctx, fast):
        """Run the test and fix loop."""
        run_test_fix_loop(
            agent=ctx.obj["agent"],
            caffeinate=ctx.obj.get("caffeinate", False),
            fast=fast,
            stream=ctx.obj.get("stream", False),
        )

    cli.add_command(test_fix, name="test-fix")
