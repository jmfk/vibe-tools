import hashlib
import json
import pathlib
import sys
from typing import Any

from vibe_tools.cost import AGENT_DEFAULT_MODEL, CostLogger, get_session_cost
from vibe_tools.testing import ProjectTester
from vibe_tools.utils import (
    PRD_DIR,
    STATE_FILE,
    ensure_dir,
    get_agent_command,
    is_merged,
    logger,
    run_agent,
    run_command,
)

BACKEND_ROOT = pathlib.Path("src")
FRONTEND_ROOT = pathlib.Path("frontend")
PROMPTS_DIR = pathlib.Path("prompts")
BASE_PROMPT_TEMPLATE = PROMPTS_DIR / "ralph_base_prompt.txt"
REVIEW_PROMPT_TEMPLATE = PROMPTS_DIR / "review_prompt.txt"
ARCHITECTURE = pathlib.Path("prds/architecture.yaml")
OVERVIEW = pathlib.Path("prds/project_overview.yaml")

MAX_ITERATIONS = 10
COMPLETION_PROMISE = "<promise>DONE</promise>"


def save_state(prd_name, iteration, output, context, phase="build"):
    """Saves the current state to a file."""
    # Load existing state to preserve completed_prds
    state = load_state() or {"completed_prds": [], "active_task": None}

    state["active_task"] = {
        "prd_name": prd_name,
        "iteration": iteration,
        "phase": phase,
        "output": output,
        "context": context,
    }
    STATE_FILE.write_text(json.dumps(state, indent=2))


def mark_prd_completed(prd_name):
    """Marks a PRD as completed in the state file."""
    state = load_state() or {"completed_prds": [], "active_task": None}
    if prd_name not in state["completed_prds"]:
        state["completed_prds"].append(prd_name)
    state["active_task"] = None
    STATE_FILE.write_text(json.dumps(state, indent=2))


def load_state():
    """Loads state from the state file if it exists."""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            # Handle legacy format
            if "prd_name" in data and "active_task" not in data:
                return {
                    "completed_prds": [],
                    "active_task": {
                        "prd_name": data.get("prd_name"),
                        "iteration": data.get("iteration", 1),
                        "phase": data.get("phase", "build"),
                        "output": data.get("output", ""),
                        "context": data.get("context", ""),
                    },
                }
            # Ensure new structure
            if "completed_prds" not in data:
                data["completed_prds"] = []
            if "active_task" not in data:
                data["active_task"] = None
            return data
        except Exception as e:
            logger.warning(f"Failed to load state file: {e}")
            return None
    return {"completed_prds": [], "active_task": None}


def clear_active_state():
    """Clears only the active task from the state file."""
    state = load_state()
    if state:
        state["active_task"] = None
        STATE_FILE.write_text(json.dumps(state, indent=2))


def clear_state():
    """Deletes the entire state file."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()


def get_pending_prds_and_estimates(agent_type, config):
    """
    Returns a list of pending PRDs and their estimated initial prompt costs.
    """
    from vibe_tools.cost import AGENT_DEFAULT_MODEL, CostLogger

    cost_logger = CostLogger(config)
    model = AGENT_DEFAULT_MODEL.get(agent_type, "unknown")

    state = load_state()
    completed_prds = state.get("completed_prds", [])
    active_task = state.get("active_task")

    resume_prd = active_task["prd_name"] if active_task else None
    active_task["iteration"] if active_task else 1

    prds = sorted(PRD_DIR.glob("prd_*.yaml"))
    results: list[dict[str, Any]] = []

    if not BASE_PROMPT_TEMPLATE.exists():
        return results

    base_prompt = BASE_PROMPT_TEMPLATE.read_text()
    architecture_content = (
        ARCHITECTURE.read_text() if ARCHITECTURE.exists() else "NOT FOUND"
    )
    overview_content = OVERVIEW.read_text() if OVERVIEW.exists() else "NOT FOUND"

    for prd_file in prds:
        project_name = prd_file.stem
        branch_name = f"feature/{project_name}"

        if resume_prd and project_name != resume_prd:
            continue

        if project_name in completed_prds:
            continue

        if is_merged(branch_name):
            continue

        # Simulate the prompt construction
        prd_content = prd_file.read_text()

        iteration_output = ""
        additional_context = ""

        if active_task and project_name == active_task.get("prd_name"):
            iteration_output = active_task.get("output", "")
            additional_context = active_task.get("context", "")

        # This matches the structure in run_ralph_agent and ralph_loop
        prompt_text = f"{base_prompt}\n{additional_context}\nPREVIOUS_OUTPUT:\n{iteration_output}\n\nRespond again until you include {COMPLETION_PROMISE}."

        combined_prompt = f"""{prompt_text}

CONTEXT FILES:
- PRD: {prd_content}
- Architecture: {architecture_content}
- Project Overview: {overview_content}

TARGET DIRECTORIES:
- Backend: {BACKEND_ROOT}
- Frontend: {FRONTEND_ROOT}

TESTING & QUALITY:
- The project uses a Makefile for testing and linting.
- Key targets: test-backend, test-frontend, test-infra, test-integration, test-regression, lint-backend, lint-frontend, lint-infra.
- INITIAL STATE: Dummy tests have been created in `tests/` and `frontend/src/` to ensure the pipeline passes.
- YOUR TASK: As you develop features, replace these dummy tests with real ones. Update the Makefile targets to run your actual test suites (e.g., changing `@exit 0` to `pytest` or `npm test`).

TASK:
Process the above according to the instructions. You are responsible for BOTH the backend (FastAPI) and the frontend (React).
Update existing files or create new ones in either directory as needed to fulfill the PRD requirements.
Include {COMPLETION_PROMISE} when you are done.
"""
        # We only estimate the initial prompt cost (input tokens)
        input_tokens = cost_logger.estimate_tokens(combined_prompt)
        cost = cost_logger.calculate_cost(model, input_tokens, 0)

        results.append(
            {
                "prd_name": project_name,
                "model": model,
                "cost_estimate": cost,
                "is_resume": project_name == resume_prd,
            }
        )

        # Once we found the resume PRD, stop skipping
        resume_prd = None

    return results


def run_ralph_agent(
    agent_type,
    prompt_text,
    prd_path,
    architecture_path,
    overview_path,
    backend_dir,
    frontend_dir,
    caffeinate=False,
):
    """
    Calls the configured agent with the combined prompt and context.
    """
    combined_prompt = f"""{prompt_text}

CONTEXT FILES:
- PRD: {prd_path}
- Architecture: {architecture_path}
- Project Overview: {overview_path}

TARGET DIRECTORIES:
- Backend: {backend_dir}
- Frontend: {frontend_dir}

TESTING & QUALITY:
- The project uses a Makefile for testing and linting.
- Key targets: test-backend, test-frontend, test-infra, test-integration, test-regression, lint-backend, lint-frontend, lint-infra.
- INITIAL STATE: Dummy tests have been created in `tests/` and `frontend/src/` to ensure the pipeline passes.
- YOUR TASK: As you develop features, replace these dummy tests with real ones. Update the Makefile targets to run your actual test suites (e.g., changing `@exit 0` to `pytest` or `npm test`).

TASK:
Process the above according to the instructions. You are responsible for BOTH the backend (FastAPI) and the frontend (React).
Update existing files or create new ones in either directory as needed to fulfill the PRD requirements.
Include {COMPLETION_PROMISE} when you are done.
"""

    cmd = get_agent_command(agent_type, combined_prompt)
    output, _ = run_agent(cmd, caffeinate=caffeinate)
    return output


def run_tests_logic(caffeinate=False):
    """Runs backend and frontend tests."""
    tester = ProjectTester()
    return tester.run_tests(caffeinate=caffeinate)


def run_review_logic(agent_type, prd_path, caffeinate=False):
    """Asks an agent to review the changes against the PRD."""
    logger.info("Running Agentic Review...")
    if not REVIEW_PROMPT_TEMPLATE.exists():
        logger.warning(
            f"Review template not found at {REVIEW_PROMPT_TEMPLATE}. Skipping review."
        )
        return "", True

    review_prompt_base = REVIEW_PROMPT_TEMPLATE.read_text()
    review_prompt = review_prompt_base.replace("{prd_path}", str(prd_path))

    cmd = get_agent_command(agent_type, review_prompt)
    output, _ = run_agent(cmd, caffeinate=caffeinate)
    return output, "<review>PASSED</review>" in output


def check_budget(budget):
    """Checks if the current session cost exceeds the budget. Returns updated budget."""
    if budget is None:
        return None

    import click

    from vibe_tools.cost import _session_runs

    current_cost = get_session_cost()
    if current_cost >= budget:
        logger.warning(
            f"\n⚠️  BUDGET REACHED: Current session cost (${current_cost:.4f}) has reached the limit of ${budget:.2f}"
        )

        # Display cost report
        click.echo("\n" + "=" * 40)
        click.echo("SESSION COST REPORT (BUDGET EXCEEDED)")
        click.echo("=" * 40)
        for run in _session_runs:
            click.echo(f"{run['phase']:<10} {run['prd'][:15]:<16} ${run['cost']:>8.4f}")
        click.echo("-" * 40)
        click.echo(f"{'TOTAL:':<27} ${current_cost:>8.4f}")
        click.echo("=" * 40)

        if click.confirm(
            "\nWould you like to increase the budget and continue?", default=True
        ):
            add_amount = click.prompt(
                "How much would you like to add to the budget (USD)?",
                type=float,
                default=5.0,
            )
            new_budget = budget + add_amount
            click.echo(f"✅ Budget increased to ${new_budget:.2f}. Continuing...")
            return new_budget
        else:
            click.echo("Aborting run due to budget limit.")
            sys.exit(0)

    return budget


def ralph_loop(
    agent="cursor-agent",
    review=False,
    tests=False,
    auto_merge=False,
    caffeinate=False,
    budget=None,
):
    from vibe_tools.cli import load_config

    config = load_config()
    cost_logger = CostLogger(config)

    if not PROMPTS_DIR.exists():
        logger.error(
            "Error: prompts directory not found. Please run 'vibe init' first."
        )
        sys.exit(1)

    if not PRD_DIR.exists():
        logger.warning(f"PRD directory {PRD_DIR} not found. Creating it.")
        PRD_DIR.mkdir(exist_ok=True)
        logger.info("No PRDs found. Exiting.")
        return

    # Ensure Makefile and dummy tests exist if tests are enabled
    if tests:
        makefile_path = pathlib.Path("Makefile")
        from vibe_tools.templates import TEMPLATES

        if not makefile_path.exists():
            logger.info("Makefile not found. Initializing with default templates...")
            makefile_content = TEMPLATES.get("Makefile")
            if makefile_content:
                makefile_path.write_text(makefile_content)
                logger.info("✅ Created default Makefile.")

        # Ensure dummy tests exist
        backend_test_dir = pathlib.Path("tests")
        ensure_dir(backend_test_dir)
        dummy_backend = backend_test_dir / "test_dummy.py"
        if not any(backend_test_dir.glob("test_*.py")):
            logger.info(f"No backend tests found. Creating {dummy_backend}")
            dummy_backend.write_text(TEMPLATES["dummy_backend_test"])

        frontend_test_dir = FRONTEND_ROOT / "src"
        ensure_dir(frontend_test_dir)
        dummy_frontend = frontend_test_dir / "dummy.test.ts"
        if not any(frontend_test_dir.glob("*.test.*")) and not any(
            frontend_test_dir.glob("*.spec.*")
        ):
            logger.info(f"No frontend tests found. Creating {dummy_frontend}")
            dummy_frontend.write_text(TEMPLATES["dummy_frontend_test"])

    ensure_dir(BACKEND_ROOT)
    ensure_dir(FRONTEND_ROOT)

    # Load existing state
    state = load_state()
    completed_prds = state.get("completed_prds", [])
    active_task = state.get("active_task")

    resume_prd = active_task["prd_name"] if active_task else None
    resume_iteration = active_task["iteration"] if active_task else 1
    resume_phase = active_task["phase"] if active_task else "build"

    if resume_prd:
        logger.info(
            f"[RESTART] Resuming {resume_prd} at iteration {resume_iteration} in phase '{resume_phase}'"
        )

    # Ensure we are on main branch
    logger.info("Ensuring we are on 'main' branch...")
    run_command(["git", "checkout", "main"])

    # Iterate only over numbered PRDs, excluding architecture, index, and overview
    prds = sorted(PRD_DIR.glob("prd_*.yaml"))
    if not prds:
        logger.info("No PRD files found (matching 'prd_*.yaml').")
        return

    try:
        for prd_file in prds:
            project_name = prd_file.stem
            branch_name = f"feature/{project_name}"

            # If we are resuming, skip until we reach the resume target
            if resume_prd and project_name != resume_prd:
                logger.info(f"Skipping {project_name} (resuming from {resume_prd})...")
                continue

            # Check if already done (merged or in completed_prds)
            if project_name in completed_prds:
                logger.info(
                    f"PRD {project_name} already marked as completed in state file. Skipping..."
                )
                continue

            # Once we reach the resume target, we don't need to skip anymore
            resume_prd = None

            logger.info(f"\n--- Running Ralph Loop for {project_name} ---")

            if is_merged(branch_name):
                logger.info(
                    f"Branch {branch_name} already merged into main. Skipping..."
                )
                # Also mark as completed if it's merged but not in state
                if project_name not in completed_prds:
                    mark_prd_completed(project_name)
                continue

            # Check if branch exists
            _, check_branch = run_command(
                ["git", "rev-parse", "--verify", branch_name], check=False
            )

            if check_branch == 0:
                logger.info(f"Branch {branch_name} already exists. Switching to it...")
                run_command(["git", "checkout", branch_name])
            else:
                logger.info(f"Creating and switching to branch: {branch_name}")
                run_command(["git", "checkout", "-b", branch_name])

            if not BASE_PROMPT_TEMPLATE.exists():
                logger.error(
                    f"Base prompt template not found at {BASE_PROMPT_TEMPLATE}. Please run 'vibe init'."
                )
                sys.exit(1)

            base_prompt = BASE_PROMPT_TEMPLATE.read_text()
            iteration_output = active_task["output"] if active_task else ""
            additional_context = active_task["context"] if active_task else ""
            start_iteration = resume_iteration
            start_phase = resume_phase

            # Clear active_task once it's been consumed
            active_task = None
            resume_iteration = 1
            resume_phase = "build"

            success = False
            last_error_hash = None
            error_repeat_count = 0

            for i in range(start_iteration, MAX_ITERATIONS + 1):
                # Phase 1: Build/Implementation
                if start_phase == "build":
                    # Check budget before agent call
                    budget = check_budget(budget)

                    logger.info(
                        f"🚀 [RALPH LOOP] [PHASE: build] (Iteration {i}/{MAX_ITERATIONS})"
                    )

                    prompt_for_iteration = f"{base_prompt}\n{additional_context}\nPREVIOUS_OUTPUT:\n{iteration_output}\n\nRespond again until you include {COMPLETION_PROMISE}."

                    output = run_ralph_agent(
                        agent,
                        prompt_for_iteration,
                        prd_file,
                        ARCHITECTURE if ARCHITECTURE.exists() else "NOT FOUND",
                        OVERVIEW if OVERVIEW.exists() else "NOT FOUND",
                        BACKEND_ROOT,
                        FRONTEND_ROOT,
                        caffeinate=caffeinate,
                    )

                    cost_logger.log_run(
                        agent=agent,
                        model=AGENT_DEFAULT_MODEL.get(agent, "unknown"),
                        prompt=prompt_for_iteration,
                        output=output,
                        prd_name=project_name,
                        iteration=i,
                        phase="build",
                        purpose="implementation",
                    )

                    iteration_output = output

                    if COMPLETION_PROMISE not in output:
                        logger.info(
                            "⏳ Agent is still working (no completion promise yet)..."
                        )
                        additional_context = ""
                        save_state(
                            project_name,
                            i + 1,
                            output,
                            additional_context,
                            phase="build",
                        )
                        continue

                    logger.info(
                        f"✅ COMPLETION PROMISE FOUND at iteration {i}. Proceeding to Quality Gates."
                    )
                    save_state(
                        project_name, i, output, additional_context, phase="test"
                    )
                    start_phase = "test"

                # Phase 2: Tests
                if start_phase == "test":
                    logger.info(
                        f"🧪 [RALPH LOOP] [PHASE: test] (Iteration {i}/{MAX_ITERATIONS})"
                    )
                    if tests:
                        test_output, tests_passed, env_failures = run_tests_logic(
                            caffeinate=caffeinate
                        )

                        if env_failures:
                            logger.error(
                                f"❌ ENVIRONMENT FAILURE DETECTED: Commands missing for targets: {', '.join(env_failures)}"
                            )
                            logger.error(
                                "The system cannot continue automatically when tools are missing from the environment."
                            )
                            logger.error(
                                "Please ensure 'npx', 'npm', and other required tools are installed and accessible."
                            )
                            sys.exit(127)

                        if not tests_passed:
                            # Loop detection
                            error_hash = hashlib.md5(test_output.encode()).hexdigest()
                            if error_hash == last_error_hash:
                                error_repeat_count += 1
                                logger.warning(
                                    f"⚠️  REPEATED FAILURE DETECTED (Count: {error_repeat_count})"
                                )
                            else:
                                error_repeat_count = 0

                            last_error_hash = error_hash

                            if error_repeat_count >= 2:
                                logger.error(
                                    "🛑 STOPPING: The system is stuck in a loop with the same test failure."
                                )
                                logger.error(
                                    "The agent is unable to fix the issue automatically. Please intervene."
                                )
                                logger.info(f"Last test output:\n{test_output}")
                                sys.exit(1)

                            logger.error(
                                "❌ Tests failed. Feeding back to agent for repair..."
                            )
                            additional_context = f"THE PREVIOUS CHANGES CAUSED TEST FAILURES:\n{test_output}"
                            save_state(
                                project_name,
                                i + 1,
                                iteration_output,
                                additional_context,
                                phase="build",
                            )
                            start_phase = "build"
                            continue
                        logger.info("✅ All tests and linting passed.")
                    else:
                        logger.info("⏩ Skipping tests as requested.")

                    save_state(
                        project_name,
                        i,
                        iteration_output,
                        additional_context,
                        phase="review",
                    )
                    start_phase = "review"

                # Phase 3: Review
                if start_phase == "review":
                    # Check budget before agent call
                    budget = check_budget(budget)

                    logger.info(
                        f"🔎 [RALPH LOOP] [PHASE: review] (Iteration {i}/{MAX_ITERATIONS})"
                    )
                    if review:
                        review_output, review_passed = run_review_logic(
                            agent, prd_file, caffeinate=caffeinate
                        )
                        cost_logger.log_run(
                            agent=agent,
                            model=AGENT_DEFAULT_MODEL.get(agent, "unknown"),
                            prompt=f"Review changes against {prd_file}",
                            output=review_output,
                            prd_name=project_name,
                            iteration=i,
                            phase="review",
                            purpose="agentic_review",
                        )
                        if not review_passed:
                            logger.error("❌ Review failed. Feeding back to agent...")
                            additional_context = f"THE PREVIOUS CHANGES FAILED CODE REVIEW:\n{review_output}"
                            save_state(
                                project_name,
                                i + 1,
                                iteration_output,
                                additional_context,
                                phase="build",
                            )
                            start_phase = "build"
                            continue
                        logger.info("✅ Review passed.")
                    else:
                        logger.info("⏩ Skipping agentic review as requested.")

                    success = True
                    break

            if success:
                # Check budget before commit agent call
                budget = check_budget(budget)

                logger.info(f"Committing changes for: {project_name}")
                commit_prompt = f"Git commit all changes in the repository. Group changes into reasonable, atomic commits based on their purpose. Write clear and descriptive commit messages. Context: These changes were generated for PRD {project_name} and passed all quality gates."
                commit_cmd = get_agent_command(agent, commit_prompt)
                commit_output, _ = run_agent(commit_cmd, caffeinate=caffeinate)
                cost_logger.log_run(
                    agent=agent,
                    model=AGENT_DEFAULT_MODEL.get(agent, "unknown"),
                    prompt=commit_prompt,
                    output=commit_output,
                    prd_name=project_name,
                    iteration=1,
                    phase="commit",
                    purpose="committing_changes",
                )

                if auto_merge:
                    logger.info(f"Merging {branch_name} into main...")
                    run_command(["git", "checkout", "main"])
                    run_command(["git", "merge", branch_name])
                else:
                    logger.info(
                        f"Auto-merge is OFF. Changes remain on branch {branch_name}."
                    )
                    run_command(["git", "checkout", "main"])

                mark_prd_completed(project_name)
            else:
                logger.error(
                    f"FAILED: Did not find completion promise within {MAX_ITERATIONS} iterations."
                )
                sys.exit(1)

    finally:
        logger.info("Ralph Loop process complete. Returning to 'main' branch...")
        run_command(["git", "checkout", "main"])

    print("All PRDs processed successfully.")
