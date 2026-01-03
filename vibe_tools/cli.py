import pathlib
import click
import json
import subprocess
from vibe_tools.utils import ensure_dir, ensure_gitignore

CONFIG_FILE = pathlib.Path(".vibe_config.json")


def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_config(config):
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    ensure_gitignore(".vibe_config.json")


def maybe_init_git():
    from vibe_tools.utils import is_git_repo

    if not is_git_repo():
        if click.confirm(
            "\nNo git repository found. Would you like to initialize one?", default=True
        ):
            try:
                subprocess.run(["git", "init"], check=True)
                click.echo("✅ Initialized empty Git repository.")
                ensure_gitignore(".vibe_config.json")
            except Exception as e:
                click.echo(f"❌ Failed to initialize Git repository: {e}")


TEMPLATES = {
    "ralph_base_prompt.txt": """You are running inside a RALPH LOOP.

This prompt will be executed repeatedly until you emit the completion promise.

TASK:
Generate full-stack code strictly according to the provided PRD.
Follow all constraints in the PRD and system instructions.

INTEGRATION RULES:
- Ensure the Frontend correctly integrates with the Backend.
- Generate TypeScript interfaces in the frontend that match data schemas in the backend.
- Create or update tests using established patterns.
- Ensure the Frontend is modern, responsive, and matches the platform vision.

GENERAL RULES:
- Do NOT ask questions.
- Do NOT explain your reasoning.
- Do NOT stop early.
- Do NOT claim completion unless ALL conditions are met.
- If something is missing or ambiguous, continue refining output until resolved or explicitly blocked.

COMPLETION CONDITIONS:
You must emit the exact string:

<promise>DONE</promise>

ONLY when:
- Backend implementation is complete.
- Frontend implementation is complete.
- Appropriate tests have been added/updated.
- No BLOCKER comments remain.
- Output is internally consistent.
- No required work is left undone.

If the completion conditions are NOT met:
- Continue working.
- Improve or extend the output.
- Do NOT emit the completion promise.

OUTPUT FORMAT:
- Output code only.
- No prose.
- No markdown.
- The completion promise must appear on its own line, at the very end.
""",
    "pdr_normalization_prompt.txt": """🔒 PRD NORMALIZATION PROMPT


You are a PRD NORMALIZER.

Your task is to convert the input PRD into a STRICT, MACHINE-CONSUMABLE FORMAT.

Rules:
- Do NOT add, infer, or improve requirements.
- Do NOT rephrase intent.
- Extract only what is explicitly stated.
- If information is missing, mark it as: MISSING.
- If a section explicitly states there are NONE or NO items, mark it as: []
- Preserve ambiguity; do not resolve it.
- Use only the section headers defined below.
- Output valid YAML only.
- DO NOT wrap the output in markdown code blocks (e.g., no ```yaml).
- No explanations.

REQUIRED SECTIONS (in this exact order):
1. SYSTEM_CONTRACT
2. DOMAIN_MODEL
3. CAPABILITIES
4. OUTPUT_TARGETS

If a section has no data, include it with value: MISSING.

BEGIN INPUT PRD
<<<
{PASTE HUMAN PRD HERE}
>>>
END INPUT PRD
""",
    "review_prompt.txt": """You are a Senior Full-Stack Developer. Review the recent changes in 'src/' and 'frontend/' against the provided PRD.

CONTEXT:
- PRD: {prd_path}

TASK:
1. Verify all requirements in the PRD are met.
2. Check for architectural consistency.
3. Check for security or performance issues.
4. Ensure frontend and backend are correctly integrated.

If everything looks correct, respond with: <review>PASSED</review>
Otherwise, list the issues and do NOT include the pass tag.
""",
    "test_fix_prompt.txt": """The codebase currently has test or linting failures. Please fix them.

ERROR OUTPUT:
{test_output}

TASK:
1. Analyze the errors provided above.
2. Fix the underlying issues in the backend or frontend.
3. Ensure that after your changes, the project builds and tests pass.
4. Include <promise>DONE</promise> in your response once you believe the issues are fixed.
""",
    "coverage_improvement_prompt.txt": """You are in TEST COVERAGE IMPROVEMENT MODE.

CURRENT COVERAGE REPORT:
{report}

TASK:
Improve the test coverage of the backend implementation. 
Focus on the files with the highest number of 'Missing' lines as shown in the report.
Create new test files or update existing ones to cover the missing lines.
Your goal is to increase the total coverage from {current_cov}% towards the target of {target_cov:.1f}%.

RULES:
- Do not break existing tests.
- Use established testing patterns for the project.
- Once you have added/updated tests that you believe significantly improve coverage, include <promise>DONE</promise> in your final response.

Output code only. No extra text.
""",
    "monitor_prompt.txt": """You are a PROGRESS INSPECTOR for an automated code generation loop.
Current Time: {timestamp}
Current Branch: {current_branch}

GIT STATUS (short):
{git_status}

RECENT DIFFS (src/):
{last_diff}

TASK:
1. Identify which PRD is likely being processed (look at branch name).
2. Summarize the progress in 'src/'.
3. Detect any "BLOCKER" messages in files or signs of failure/stalling.
4. Provide a HEALTH STATUS: [HEALTHY], [STALLED], or [FAILED].
5. Keep it very concise (max 10 lines).
""",
}


@click.group(invoke_without_command=True)
@click.option(
    "--agent",
    type=click.Choice(["cursor-agent", "claude", "antigravity"]),
    default="cursor-agent",
    help="Select the agent to use.",
)
@click.option(
    "--caffeinate",
    is_flag=True,
    default=None,
    help="Use caffeinate to prevent sleep during long-running tasks.",
)
@click.version_option(version="0.1.0")
@click.pass_context
def cli(ctx, agent, caffeinate):
    ctx.ensure_object(dict)
    ctx.obj["agent"] = agent

    config = load_config()
    if caffeinate is None:
        caffeinate = config.get("caffeinate", False)
    ctx.obj["caffeinate"] = caffeinate

    if ctx.invoked_subcommand is None:
        click.echo("vibe-tools configuration:")
        click.echo(f"  Agent: {agent}")
        click.echo(f"  Caffeinate: {'ON' if caffeinate else 'OFF'}")

        ralph_config = config.get("ralph", {})
        if ralph_config:
            click.echo("  Ralph Default Config:")
            click.echo(
                f"    Tests:      {'ON' if ralph_config.get('tests') else 'OFF'}"
            )
            click.echo(
                f"    Review:     {'ON' if ralph_config.get('review') else 'OFF'}"
            )
            click.echo(
                f"    Auto-merge: {'ON' if ralph_config.get('auto_merge') else 'OFF'}"
            )
        else:
            click.echo("  Ralph Default Config: Not set (will prompt on first run)")

        prompts_init = pathlib.Path("prompts").exists()
        click.echo(f"  Initialized: {'Yes (prompts/ found)' if prompts_init else 'No'}")

        specs_dir = (
            pathlib.Path("specs")
            if pathlib.Path("specs").exists()
            else pathlib.Path("spec")
        )
        click.echo(
            f"  Specs Directory: {specs_dir if specs_dir.exists() else 'Not found (defaults to specs/)'}"
        )

        if not prompts_init:
            click.echo("\nRun 'vibe init' to set up templates.")

        click.echo("\nAvailable commands:")
        for command in sorted(cli.list_commands(ctx)):
            cmd_obj = cli.get_command(ctx, command)
            click.echo(f"  {command:<10} {cmd_obj.get_short_help_str()}")

        click.echo("\nRun 'vibe --help' for full options.")


@cli.command()
def init():
    """Initialize the prompts directory and default templates."""
    maybe_init_git()
    prompts_dir = pathlib.Path("prompts")
    ensure_dir(prompts_dir)

    for filename, content in TEMPLATES.items():
        file_path = prompts_dir / filename
        if not file_path.exists():
            print(f"Creating template: {file_path}")
            file_path.write_text(content)
        else:
            print(f"Template already exists: {file_path}")


@cli.command()
@click.option(
    "--review/--no-review",
    is_flag=True,
    default=None,
    help="Enable/disable agentic review.",
)
@click.option(
    "--tests/--no-tests",
    is_flag=True,
    default=None,
    help="Enable/disable running tests.",
)
@click.option(
    "--auto-merge/--no-auto-merge",
    is_flag=True,
    default=None,
    help="Enable/disable automatic merge.",
)
@click.pass_context
def ralph(ctx, review, tests, auto_merge):
    """Run the Ralph loop for processing PRDs."""
    maybe_init_git()
    agent = ctx.obj.get("agent", "cursor-agent")
    config = load_config().get("ralph", {})

    # Use config if not explicitly provided via CLI
    if review is None:
        review = config.get("review", False)
    if tests is None:
        tests = config.get("tests", False)
    if auto_merge is None:
        auto_merge = config.get("auto_merge", False)

    # If everything is still False (and we have no config file), prompt the user
    if not CONFIG_FILE.exists() and not any([review, tests, auto_merge]):
        click.echo("\n⚠️ Ralph is not yet configured for quality gates.")
        
        tests = click.confirm(
            "Enable Tests (auto-discover backend and frontend tests)?",
            default=True,
        )
        if tests:
            click.echo("✅ Tests enabled.")

        review = click.confirm(
            "Enable Agentic Review (agent verifies changes against PRD)?",
            default=True,
        )
        if review:
            click.echo("✅ Agentic Review enabled.")

        auto_merge = click.confirm(
            "Enable Auto-merge (automatically merge into main if quality gates pass)?",
            default=False,
        )
        if auto_merge:
            click.echo("✅ Auto-merge enabled.")

        caffeinate = ctx.obj.get("caffeinate", False)
        if not caffeinate:
            if click.confirm(
                "Would you like to use 'caffeinate' to prevent system sleep during long runs?",
                default=True,
            ):
                caffeinate = True
                ctx.obj["caffeinate"] = caffeinate
                click.echo("✅ Enabled Caffeinate.")

        if click.confirm(
            "Save these settings as default in .vibe_config.json?", default=True
        ):
            save_config(
                {
                    "ralph": {
                        "review": review,
                        "tests": tests,
                        "auto_merge": auto_merge,
                    },
                    "caffeinate": caffeinate,
                }
            )
            click.echo("✅ Configuration saved.")

    click.echo("\n--- Ralph Loop Configuration ---")
    click.echo(f"Agent:      {agent}")
    click.echo(f"Review:     {'ON' if review else 'OFF'}")
    click.echo(f"Tests:      {'ON' if tests else 'OFF'}")
    click.echo(f"Auto-merge: {'ON' if auto_merge else 'OFF'}")

    click.echo("\nWorkflow:")
    click.echo("1. Ensure 'main' branch.")
    click.echo("2. Sequentially process all 'prd_*.yaml' in 'prds/'.")
    click.echo(
        "3. Create feature branch, run up to 10 agent iterations for implementation."
    )
    click.echo("4. Run quality gates (tests/review) if enabled.")
    click.echo("5. Commit and optionally merge changes.")

    if not click.confirm("\nProceed with Ralph loop?", default=True):
        click.echo("Aborted.")
        return

    from vibe_tools.ralph import ralph_loop

    ralph_loop(
        agent=agent,
        review=review,
        tests=tests,
        auto_merge=auto_merge,
        caffeinate=ctx.obj.get("caffeinate", False),
    )


@cli.command()
@click.pass_context
def test_fix(ctx):
    """Run the test and fix loop."""
    from vibe_tools.test_fix import test_fix_loop

    test_fix_loop(agent=ctx.obj["agent"], caffeinate=ctx.obj.get("caffeinate", False))


@cli.command()
@click.pass_context
def coverage(ctx):
    """Run the coverage improvement loop."""
    from vibe_tools.coverage import improve_coverage_loop

    improve_coverage_loop(
        agent=ctx.obj["agent"], caffeinate=ctx.obj.get("caffeinate", False)
    )


@cli.command()
@click.argument("input_file", required=False)
@click.option(
    "--yes", "-y", is_flag=True, help="Automatically overwrite existing PRDs."
)
@click.pass_context
def normalize(ctx, input_file, yes):
    """Normalize human-written PRDs from specs/ into machine-consumable YAML in prds/."""
    maybe_init_git()
    from vibe_tools.normalize import normalize_prd

    normalize_prd(
        agent=ctx.obj["agent"],
        input_file=input_file,
        auto_overwrite=yes,
        caffeinate=ctx.obj.get("caffeinate", False),
    )


@cli.command()
@click.option(
    "--interval",
    type=int,
    default=60,
    help="Monitoring interval in seconds (default: 60).",
)
@click.pass_context
def monitor(ctx, interval):
    """Monitor the progress of automated generation."""
    from vibe_tools.monitor import run_monitor

    run_monitor(agent=ctx.obj["agent"], interval=interval)


if __name__ == "__main__":
    cli()
