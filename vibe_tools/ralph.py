import pathlib
import sys
import json


from vibe_tools.utils import (
    run_command,
    run_agent,
    get_agent_command,
    ensure_dir,
    is_merged,
    PRD_DIR,
    STATE_FILE,
    logger,
)
from vibe_tools.testing import ProjectTester

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


def ralph_loop(
    agent="cursor-agent", review=False, tests=False, auto_merge=False, caffeinate=False
):
    from vibe_tools.utils import rotate_log

    rotate_log()

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
            logger.info(f"Branch {branch_name} already merged into main. Skipping...")
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

        for i in range(start_iteration, MAX_ITERATIONS + 1):
            # Phase 1: Build/Implementation
            if start_phase == "build":
                logger.info(f"[RALPH LOOP] [PHASE: build] (Iteration {i})")

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

                iteration_output = output

                if COMPLETION_PROMISE not in output:
                    additional_context = ""
                    save_state(
                        project_name, i + 1, output, additional_context, phase="build"
                    )
                    continue

                logger.info(
                    f"COMPLETION PROMISE FOUND at iteration {i}. Proceeding to Quality Gates."
                )
                save_state(project_name, i, output, additional_context, phase="test")
                start_phase = "test"

            # Phase 2: Tests
            if start_phase == "test":
                logger.info(f"[RALPH LOOP] [PHASE: test] (Iteration {i})")
                if tests:
                    test_output, tests_passed = run_tests_logic(caffeinate=caffeinate)
                    if not tests_passed:
                        logger.error("❌ Tests failed. Feeding back to agent...")
                        additional_context = (
                            f"THE PREVIOUS CHANGES CAUSED TEST FAILURES:\n{test_output}"
                        )
                        save_state(
                            project_name,
                            i + 1,
                            iteration_output,
                            additional_context,
                            phase="build",
                        )
                        start_phase = "build"
                        continue
                    logger.info("✅ Tests passed.")
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
                logger.info(f"[RALPH LOOP] [PHASE: review] (Iteration {i})")
                if review:
                    review_output, review_passed = run_review_logic(
                        agent, prd_file, caffeinate=caffeinate
                    )
                    if not review_passed:
                        logger.error("❌ Review failed. Feeding back to agent...")
                        additional_context = (
                            f"THE PREVIOUS CHANGES FAILED CODE REVIEW:\n{review_output}"
                        )
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
            logger.info(f"Committing changes for: {project_name}")
            commit_prompt = f"Git commit all changes in the repository. Group changes into reasonable, atomic commits based on their purpose. Write clear and descriptive commit messages. Context: These changes were generated for PRD {project_name} and passed all quality gates."
            commit_cmd = get_agent_command(agent, commit_prompt)
            run_agent(commit_cmd, caffeinate=caffeinate)

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
            logger.info("Reverting to 'main' branch.")
            run_command(["git", "checkout", "main"])
            sys.exit(1)

    print("All PRDs processed successfully.")
