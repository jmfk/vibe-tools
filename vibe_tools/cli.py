import os
import pathlib
import click
from vibe_tools.utils import ensure_dir

TEMPLATES = {
    "ralph_base_prompt.txt": """You are running inside a RALPH LOOP.

This prompt will be executed repeatedly until you emit the completion promise.

TASK:
Generate full-stack code (Backend FastAPI and Frontend React/TypeScript) strictly according to the provided PRD.
Follow all constraints in the PRD and system instructions.

INTEGRATION RULES:
- Ensure the Frontend uses the `apiClient` in `frontend/src/api/client.ts`.
- Generate TypeScript interfaces in the frontend that match Pydantic schemas in the backend.
- Create or update backend tests in `tests/` using the established `pytest` patterns.
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
- Backend implementation (models, schemas, services, endpoints) is complete.
- Frontend implementation (pages, components, api integration) is complete.
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
2. Fix the underlying issues in the backend (FastAPI) or frontend (React).
3. Ensure that after your changes, the project builds and tests pass.
4. Include <promise>DONE</promise> in your response once you believe the issues are fixed.
""",
    "coverage_improvement_prompt.txt": """You are in TEST COVERAGE IMPROVEMENT MODE.

CURRENT COVERAGE REPORT:
{report}

TASK:
Improve the test coverage of the backend implementation. 
Focus on the files with the highest number of 'Missing' lines as shown in the report.
Create new test files in 'tests/' or update existing ones to cover the missing lines.
Your goal is to increase the total coverage from {current_cov}% towards the target of {target_cov:.1f}%.

RULES:
- Do not break existing tests (run 'make test' to verify).
- Use pytest and tortoise-orm testing patterns as established in 'tests/conftest.py'.
- Work directly in the 'tests/' and 'src/' directories if needed (but primarily 'tests/').
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
"""
}

@click.group(invoke_without_command=True)
@click.option("--agent", type=click.Choice(["cursor-agent", "claude", "antigravity"]), default="cursor-agent", help="Select the agent to use.")
@click.version_option(version="0.1.0")
@click.pass_context
def cli(ctx, agent):
    ctx.ensure_object(dict)
    ctx.obj['agent'] = agent
    
    if ctx.invoked_subcommand is None:
        click.echo("vibe-tools configuration:")
        click.echo(f"  Agent: {agent}")
        
        prompts_init = pathlib.Path("prompts").exists()
        click.echo(f"  Initialized: {'Yes (prompts/ found)' if prompts_init else 'No'}")
        
        specs_dir = pathlib.Path("specs") if pathlib.Path("specs").exists() else pathlib.Path("spec")
        click.echo(f"  Specs Directory: {specs_dir if specs_dir.exists() else 'Not found (defaults to specs/)'}")
        
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
@click.option("--review", is_flag=True, default=False, help="Enable agentic review (default: off).")
@click.option("--no-tests", "tests", flag_value=False, default=True, help="Disable running tests (default: tests on).")
@click.option("--auto-merge", is_flag=True, default=False, help="Automatically merge branches into main (default: off).")
@click.pass_context
def ralph(ctx, review, tests, auto_merge):
    """Run the Ralph loop for processing PRDs."""
    from vibe_tools.ralph import ralph_loop
    ralph_loop(agent=ctx.obj['agent'], review=review, tests=tests, auto_merge=auto_merge)

@cli.command()
@click.pass_context
def test_fix(ctx):
    """Run the test and fix loop."""
    from vibe_tools.test_fix import test_fix_loop
    test_fix_loop(agent=ctx.obj['agent'])

@cli.command()
@click.pass_context
def coverage(ctx):
    """Run the coverage improvement loop."""
    from vibe_tools.coverage import improve_coverage_loop
    improve_coverage_loop(agent=ctx.obj['agent'])

@cli.command()
@click.argument("input_file", required=False)
@click.option("--yes", "-y", is_flag=True, help="Automatically overwrite existing PRDs.")
@click.pass_context
def normalize(ctx, input_file, yes):
    """Normalize human-written PRDs from specs/ into machine-consumable YAML in prds/."""
    from vibe_tools.normalize import normalize_prd
    normalize_prd(agent=ctx.obj['agent'], input_file=input_file, auto_overwrite=yes)

@cli.command()
@click.option("--interval", type=int, default=60, help="Monitoring interval in seconds (default: 60).")
@click.pass_context
def monitor(ctx, interval):
    """Monitor the progress of automated generation."""
    from vibe_tools.monitor import run_monitor
    run_monitor(agent=ctx.obj['agent'], interval=interval)

if __name__ == "__main__":
    cli()
