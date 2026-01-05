import hashlib
import json
import pathlib
import sys
import click
from typing import Any

from vibe_tools.cost import AGENT_DEFAULT_MODEL, CostLogger, get_session_cost
from vibe_tools.testing import ProjectTester
from vibe_tools.utils import (
    INSTRUCTIONS_DIR,
    PRD_DIR,
    STATE_FILE,
    PROJECT_STATE_FILE,
    ARCHITECTURE,
    ARCHITECTURE_CURRENT,
    OVERVIEW,
    PROJECT_PLAN,
    INFRA,
    INFRA_CURRENT,
    CICD,
    CICD_CURRENT,
    TESTING_CONFIG,
    TESTING_CURRENT,
    collect_prd_files,
    ensure_dir,
    get_agent_command,
    get_instructions_context,
    get_latest_context_file,
    get_main_branch,
    is_dirty,
    logger,
    run_agent,
    run_command,
    load_project_state,
    save_project_state,
    get_file_hash,
)

BACKEND_ROOT = pathlib.Path("backend")
FRONTEND_ROOT = pathlib.Path("frontend")
PROMPTS_DIR = pathlib.Path("prompts")
BASE_PROMPT_TEMPLATE = PROMPTS_DIR / "ralph_base_prompt.txt"
PLANNER_PROMPT_TEMPLATE = PROMPTS_DIR / "planner_prompt.txt"
REVIEW_PROMPT_TEMPLATE = PROMPTS_DIR / "review_prompt.txt"

MAX_ITERATIONS = 10
COMPLETION_PROMISE = "<promise>DONE</promise>"


class RalphLoop:
    """Core reconciliation loop between Desired State and Actual State."""

    def __init__(
        self,
        name: str,
        desired_file: pathlib.Path,
        current_file: pathlib.Path,
        agent: str = "cursor-agent",
        stream: bool = False,
        caffeinate: bool = False,
    ):
        self.name = name
        self.desired_file = desired_file
        self.current_file = current_file
        self.agent = agent
        self.stream = stream
        self.caffeinate = caffeinate

    def run(self) -> bool:
        """Executes the reconciliation loop."""
        logger.info(f"🔄 Starting {self.name} Loop...")

        if not self.desired_file.exists():
            logger.error(f"❌ Desired file {self.desired_file} not found.")
            return False

        # 1. Compare Desired vs Current
        desired_hash = get_file_hash(self.desired_file)
        current_content = (
            self.current_file.read_text() if self.current_file.exists() else "NOT FOUND"
        )

        # 2. Prepare prompt
        prompt = f"""You are in the '{self.name}' phase of the project lifecycle.
Your goal is to reconcile the DESIRED state (defined in {self.desired_file.name}) with the ACTUAL state (described in {self.current_file.name} and the current codebase).

DESIRED STATE ({self.desired_file.name}):
{self.desired_file.read_text()}

ACTUAL STATE ({self.current_file.name}):
{current_content}

INSTRUCTIONS:
1. Examine the current codebase and the actual state.
2. Perform any necessary actions (coding, configuration, setup) to match the desired state.
3. Update {self.current_file.name} to accurately reflect the new actual state once complete.
4. Include {COMPLETION_PROMISE} in your response when the reconciliation is successful.
"""
        # 3. Run Agent
        cmd = get_agent_command(self.agent, prompt)
        output, code = run_agent(cmd, caffeinate=self.caffeinate, stream=self.stream)

        if code == 0 and COMPLETION_PROMISE in output:
            logger.info(f"✅ {self.name} reconciliation successful.")
            return True
        else:
            logger.error(f"❌ {self.name} reconciliation failed or incomplete.")
            return False


def run_planner_agent(agent: str, stream: bool = False) -> bool:
    """Runs the Planner Agent to generate project-plan.yaml."""
    architecture = ARCHITECTURE.read_text() if ARCHITECTURE.exists() else "NOT FOUND"
    prds = ""
    for prd_file in collect_prd_files():
        prds += f"\n--- {prd_file.name} ---\n{prd_file.read_text()}\n"

    if PLANNER_PROMPT_TEMPLATE.exists():
        prompt_base = PLANNER_PROMPT_TEMPLATE.read_text()
    else:
        from vibe_tools.templates import TEMPLATES

        prompt_base = TEMPLATES.get("planner_prompt.txt", "")

    prompt = f"""{prompt_base}

ARCHITECTURE:
{architecture}

PRDS:
{prds}
"""
    cmd = get_agent_command(agent, prompt)
    output, code = run_agent(cmd, stream=stream)
    return code == 0 and COMPLETION_PROMISE in output


def implementation_loop(agent: str, stream: bool = False) -> bool:
    """Executes the implementation phase based on project-plan.yaml."""
    if not PROJECT_PLAN.exists():
        logger.error(f"❌ {PROJECT_PLAN} not found.")
        return False

    try:
        import yaml

        plan_data = yaml.safe_load(PROJECT_PLAN.read_text())
    except Exception as e:
        logger.error(f"Failed to parse {PROJECT_PLAN}: {e}")
        return False

    steps = plan_data.get("steps", [])
    if not steps:
        logger.warning("No steps found in project-plan.yaml.")
        return True

    for step in steps:
        if step.get("status") == "completed":
            continue

        logger.info(f"🚀 Executing Step: {step.get('title')} ({step.get('id')})")

        prompt = f"""You are the Implementation Agent. Your task is to execute a specific step from the project plan.

STEP TO EXECUTE:
Title: {step.get('title')}
Description: {step.get('description')}
Success Criteria:
{chr(10).join(['- ' + c for c in step.get('success_criteria', [])])}

TASK:
1. Implement the code, tests, and configuration required for THIS STEP ONLY.
2. Verify the changes against the success criteria.
3. Update {PROJECT_PLAN.name} to set status of step '{step.get('id')}' to 'completed'.
4. Include {COMPLETION_PROMISE} when the step is finished.
"""
        cmd = get_agent_command(agent, prompt)
        output, code = run_agent(cmd, stream=stream)

        if code != 0 or COMPLETION_PROMISE not in output:
            logger.error(f"❌ Failed at step {step.get('id')}.")
            return False

    return True


def _switch_to_main():
    """Helper to commit dirty changes on feature branches before switching to main."""
    main_branch = get_main_branch()
    if is_dirty():
        current_branch, _ = run_command(
            ["git", "branch", "--show-current"], check=False
        )
        current_branch = current_branch.strip()
        if current_branch and current_branch != main_branch:
            logger.info(
                f"Uncommitted changes detected on '{current_branch}'. Committing before switching to '{main_branch}'..."
            )
            run_command(["git", "add", "."], check=False)
            run_command(
                [
                    "git",
                    "commit",
                    "-m",
                    f"vibe ralph: automatic commit of partial work on {current_branch}",
                ],
                check=False,
            )
        else:
            logger.warning(
                f"Uncommitted changes detected on '{main_branch}'. Please commit or stash them manually."
            )

    logger.debug(f"Switching to {main_branch}...")
    stdout, code = run_command(["git", "checkout", main_branch], check=False)
    if code != 0:
        logger.error(f"Failed to switch to {main_branch}: {stdout}")


def _switch_to_branch(branch_name, agent, project_name, caffeinate=False, stream=False):
    """Robustly switches to a feature branch, using AI rescue if needed."""
    # Check if we are already on this branch
    stdout, _ = run_command(["git", "branch", "--show-current"], check=False)
    if stdout.strip() == branch_name:
        logger.info(f"Already on branch '{branch_name}'.")
        return

    # Check if branch exists in git
    _, code = run_command(["git", "rev-parse", "--verify", branch_name], check=False)
    branch_exists = code == 0

    if branch_exists:
        logger.info(f"Branch '{branch_name}' already exists. Switching...")
        output, code = run_command(["git", "checkout", branch_name], check=False)
    else:
        logger.info(f"Creating and switching to branch: {branch_name}")
        output, code = run_command(["git", "checkout", "-b", branch_name], check=False)

    if code != 0:
        logger.warning(
            f"Git operation failed for branch '{branch_name}': {output}. Calling agent to sort it out..."
        )
        git_status, _ = run_command(["git", "status"], check=False)
        prompt = f"""A git operation failed while trying to switch to branch '{branch_name}' for PRD '{project_name}'.

ERROR:
{output}

CURRENT GIT STATUS:
{git_status}

TASK:
Please resolve this git issue so the automated pipeline can continue. 
You may need to stash changes, commit them, reset the branch, or merge. 
Ensure the end state is that we are on branch '{branch_name}' and ready to work.
"""
        cmd = get_agent_command(agent, prompt)
        run_agent(cmd, caffeinate=caffeinate, stream=stream)

        # Final attempt after agent fix
        final_output, final_code = run_command(
            ["git", "checkout", branch_name], check=False
        )
        if final_code != 0:
            logger.error(
                f"Agent was unable to resolve git conflict. Final error: {final_output}"
            )
            sys.exit(1)


def save_state(prd_name, iteration, output, context, phase="build"):
    """Saves the current state to a file."""
    # Load existing state to preserve completed_prds
    state = load_state() or {
        "completed_prds": [],
        "started_prds": [],
        "active_task": None,
    }

    if prd_name not in state.get("started_prds", []):
        if "started_prds" not in state:
            state["started_prds"] = []
        state["started_prds"].append(prd_name)

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
    state = load_state() or {
        "completed_prds": [],
        "started_prds": [],
        "active_task": None,
    }
    if prd_name not in state["completed_prds"]:
        state["completed_prds"].append(prd_name)
    if prd_name in state.get("started_prds", []):
        state["started_prds"].remove(prd_name)
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
                    "started_prds": (
                        [data.get("prd_name")] if data.get("prd_name") else []
                    ),
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
            if "started_prds" not in data:
                data["started_prds"] = []
            if "active_task" not in data:
                data["active_task"] = None
            return data
        except Exception as e:
            logger.warning(f"Failed to load state file: {e}")
            return None
    return {"completed_prds": [], "started_prds": [], "active_task": None}


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

    prds = collect_prd_files()
    results: list[dict[str, Any]] = []

    if not BASE_PROMPT_TEMPLATE.exists():
        return results

    base_prompt = BASE_PROMPT_TEMPLATE.read_text()
    architecture_content = (
        ARCHITECTURE.read_text() if ARCHITECTURE.exists() else "NOT FOUND"
    )
    overview_content = OVERVIEW.read_text() if OVERVIEW.exists() else "NOT FOUND"
    infra_content = INFRA.read_text() if INFRA.exists() else "NOT FOUND"
    cicd_content = CICD.read_text() if CICD.exists() else "NOT FOUND"
    instructions_content = get_instructions_context()

    for prd_file in prds:
        project_name = prd_file.stem

        if resume_prd and project_name != resume_prd:
            continue

        if project_name in completed_prds:
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
- Infrastructure: {infra_content}
- CI/CD: {cicd_content}

{instructions_content}

TARGET DIRECTORIES:
- Backend: {BACKEND_ROOT}
- Frontend: {FRONTEND_ROOT}

TESTING & QUALITY:
- The project uses a Makefile for testing and linting.
- Key targets: test-backend, test-frontend, test-infra, test-integration, test-regression, lint-backend, lint-frontend, lint-infra.
- INITIAL STATE: Dummy tests have been created in `{BACKEND_ROOT}/tests/` and `frontend/src/` to ensure the pipeline passes.
- YOUR TASK: As you develop features, replace these dummy tests with real ones. Update the Makefile targets to run your actual test suites (e.g., changing `@exit 0` to `pytest` or `npm test`).
- BACKEND STRUCTURE: The backend source code lives in `{BACKEND_ROOT}/`. Tests must be placed in `{BACKEND_ROOT}/tests/`.

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
    backend_dir,
    frontend_dir,
    caffeinate=False,
    stream=False,
):
    """
    Calls the configured agent with the combined prompt and context.
    """
    instructions_content = get_instructions_context()
    architecture_content = (
        ARCHITECTURE.read_text() if ARCHITECTURE.exists() else "NOT FOUND"
    )
    overview_content = OVERVIEW.read_text() if OVERVIEW.exists() else "NOT FOUND"
    infra_content = INFRA.read_text() if INFRA.exists() else "NOT FOUND"
    cicd_content = CICD.read_text() if CICD.exists() else "NOT FOUND"

    combined_prompt = f"""{prompt_text}

CONTEXT FILES:
- PRD: {prd_path}
- Architecture: {architecture_content}
- Project Overview: {overview_content}
- Infrastructure: {infra_content}
- CI/CD: {cicd_content}

{instructions_content}

TARGET DIRECTORIES:
- Backend: {backend_dir}
- Frontend: {frontend_dir}

TESTING & QUALITY:
- The project uses a Makefile for testing and linting.
- Key targets: test-backend, test-frontend, test-infra, test-integration, test-regression, lint-backend, lint-frontend, lint-infra.
- INITIAL STATE: Dummy tests have been created in `{backend_dir}/tests/` and `frontend/src/` to ensure the pipeline passes.
- YOUR TASK: As you develop features, replace these dummy tests with real ones. Update the Makefile targets to run your actual test suites (e.g., changing `@exit 0` to `pytest` or `npm test`).
- BACKEND STRUCTURE: The backend source code lives in `{backend_dir}/`. Tests must be placed in `{backend_dir}/tests/`.

TASK:
Process the above according to the instructions. You are responsible for BOTH the backend (FastAPI) and the frontend (React).
Update existing files or create new ones in either directory as needed to fulfill the PRD requirements.
Include {COMPLETION_PROMISE} when you are done.
"""

    cmd = get_agent_command(agent_type, combined_prompt)
    output, _ = run_agent(cmd, caffeinate=caffeinate, stream=stream)
    return output


def run_tests_logic(caffeinate=False, fast=False):
    """Runs backend and frontend tests."""
    tester = ProjectTester()
    return tester.run_tests(caffeinate=caffeinate, changed_only=fast)


def ensure_project_dependencies(caffeinate=False):
    """Ensures that project dependencies (npm, pip) are installed."""
    # 1. Backend dependencies
    if (
        pathlib.Path("pyproject.toml").exists()
        or pathlib.Path("requirements.txt").exists()
    ):
        logger.info("Checking backend dependencies...")
        # Check if ruff or pytest is missing (common indicators)
        _, ruff_code = run_command(["ruff", "--version"], check=False)
        _, pytest_code = run_command(["pytest", "--version"], check=False)

        if ruff_code != 0 or pytest_code != 0:
            logger.info("Backend tools (ruff/pytest) missing. Attempting to install...")
            if pathlib.Path("pyproject.toml").exists():
                run_command(
                    [sys.executable, "-m", "pip", "install", "-e", "."],
                    caffeinate=caffeinate,
                )
            elif pathlib.Path("requirements.txt").exists():
                run_command(
                    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                    caffeinate=caffeinate,
                )

    # 2. Frontend dependencies
    frontend_dir = pathlib.Path("frontend")
    if frontend_dir.exists() and (frontend_dir / "package.json").exists():
        node_modules = frontend_dir / "node_modules"
        if not node_modules.exists():
            logger.info("Frontend node_modules missing. Running npm install...")
            run_command(
                ["npm", "install", "--prefix", "frontend"], caffeinate=caffeinate
            )


def run_review_logic(agent_type, prd_path, caffeinate=False, stream=False):
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
    output, _ = run_agent(cmd, caffeinate=caffeinate, stream=stream)
    return output, "<review>PASSED</review>" in output


def run_coverage_logic(config, caffeinate=False):
    """Checks if coverage targets are met for all components."""
    logger.info("Checking coverage targets...")
    tester = ProjectTester()
    targets = config.get(
        "coverage_targets", {"backend": 85, "frontend": 85, "infra": 85}
    )

    results = []
    all_passed = True
    combined_report = ""

    # Check each component that has a directory/config
    components = []
    if BACKEND_ROOT.exists():
        components.append("backend")
    if FRONTEND_ROOT.exists():
        components.append("frontend")
    if pathlib.Path("vibe_tools").exists():
        components.append("infra")

    for component in components:
        target = targets.get(component, 85)
        report, current = tester.get_coverage_report(
            component=component, caffeinate=caffeinate
        )
        combined_report += f"\n--- COVERAGE REPORT: {component.upper()} ---\n{report}\n"

        if current < target:
            all_passed = False
            results.append(
                f"❌ {component.capitalize()}: {current}% (Target: {target}%)"
            )
        else:
            results.append(
                f"✅ {component.capitalize()}: {current}% (Target: {target}%)"
            )

    status_message = "\n".join(results)
    return combined_report, status_message, all_passed


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
    coverage=False,
    auto_merge=False,
    caffeinate=False,
    budget=None,
    fast=False,
    stream=False,
):
    from vibe_tools.cli import load_config

    config = load_config()
    cost_logger = CostLogger(config)

    # Environment health check
    from vibe_tools.utils import check_env_health

    if not check_env_health():
        logger.warning("\n⚠️  Environment health check failed!")

        # 1. Try quick fix first
        if click.confirm(
            "Would you like to run 'vibe-setup deps' to install missing tools?",
            default=True,
        ):
            from vibe_tools.setup import deps as setup_deps

            try:
                setup_deps.callback()
                if check_env_health():
                    logger.info("✅ Environment is now healthy.")
                else:
                    logger.warning(
                        "⚠️  Environment still unhealthy after installing dependencies."
                    )
            except Exception as e:
                logger.error(f"❌ Failed to install dependencies: {e}")

        # 2. If still unhealthy, offer full setup
        if not check_env_health():
            if click.confirm(
                "Would you like to run 'vibe-setup env' for a full environment setup?",
                default=True,
            ):
                # Run the env setup command logic
                from vibe_tools.setup import env as setup_env

            # Note: click.Context is needed if we want to call it exactly like the CLI
            # but we can just call the function directly for simplicity here
            try:
                # We need to provide a default python version if not specified
                setup_env.callback(python_version="3.11.10")
                # Re-check after setup
                if not check_env_health():
                    logger.error(
                        "❌ Environment still unhealthy after setup. Please fix it manually."
                    )
                    sys.exit(1)
            except Exception as e:
                logger.error(f"❌ Failed to setup environment: {e}")
                sys.exit(1)
        else:
            logger.error("Aborting Ralph Loop due to unhealthy environment.")
            sys.exit(1)

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
        # Ensure dependencies are installed before running tests
        ensure_project_dependencies(caffeinate=caffeinate)

        makefile_path = pathlib.Path("Makefile")
        from vibe_tools.templates import TEMPLATES

        if not makefile_path.exists():
            logger.info("Makefile not found. Initializing with default templates...")
            makefile_content = TEMPLATES.get("Makefile")
            if makefile_content:
                makefile_path.write_text(makefile_content)
                logger.info("✅ Created default Makefile.")

        # Ensure dummy tests exist
        backend_test_dir = BACKEND_ROOT / "tests"
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
    main_branch = get_main_branch()
    logger.info(f"Ensuring we are on '{main_branch}' branch...")
    _switch_to_main()

    # Iterate only over numbered PRDs, excluding architecture, index, and overview
    prds = collect_prd_files()
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

            # Switch to feature branch
            _switch_to_branch(
                branch_name, agent, project_name, caffeinate=caffeinate, stream=stream
            )

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
            env_fix_attempts = 0

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
                        BACKEND_ROOT,
                        FRONTEND_ROOT,
                        caffeinate=caffeinate,
                        stream=stream,
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
                            if env_fix_attempts < 2:
                                # Try to identify specific missing tools from the output
                                logger.warning(
                                    f"⚠️  ENVIRONMENT FAILURE DETECTED in targets: {', '.join(env_failures)}"
                                )
                                logger.info(
                                    "Attempting to self-heal environment issues..."
                                )

                                env_fix_prompt = f"""The following environment issues were detected while running quality gates:
{test_output}

TARGETS WITH FAILURES: {', '.join(env_failures)}

TASK:
1. Identify missing tools or configuration issues (e.g., 'ruff' missing, 'next' not found, incorrect node/python version).
2. Fix the environment by installing missing packages, updating the Makefile, or adjusting paths.
3. You may use terminal commands like 'vibe-setup deps', 'pip install', 'npm install', or 'brew install'.
4. Ensure the end state allows 'make {env_failures[0]}' (and other failed targets) to run successfully.
5. Include <promise>DONE</promise> in your response once you have attempted the fix.
"""
                                cmd = get_agent_command(agent, env_fix_prompt)
                                fix_output, _ = run_agent(
                                    cmd, caffeinate=caffeinate, stream=stream
                                )

                                env_fix_attempts += 1
                                if COMPLETION_PROMISE in fix_output:
                                    logger.info(
                                        "✅ Agent claimed to fix the environment. Retrying tests..."
                                    )
                                    start_phase = "test"
                                    continue
                                else:
                                    logger.error(
                                        "❌ Agent was unable to resolve environment issues."
                                    )

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
                        phase="coverage",
                    )
                    start_phase = "coverage"

                # Phase 3: Coverage
                if start_phase == "coverage":
                    logger.info(
                        f"📊 [RALPH LOOP] [PHASE: coverage] (Iteration {i}/{MAX_ITERATIONS})"
                    )
                    if coverage:
                        cov_report, cov_status, cov_passed = run_coverage_logic(
                            config, caffeinate=caffeinate
                        )

                        if not cov_passed:
                            logger.error(
                                f"❌ Coverage targets not met:\n{cov_status}\nFeeding back to agent..."
                            )
                            additional_context = f"THE PREVIOUS CHANGES DO NOT MEET COVERAGE TARGETS:\n{cov_status}\n\nDETAILED REPORT:\n{cov_report}"
                            save_state(
                                project_name,
                                i + 1,
                                iteration_output,
                                additional_context,
                                phase="build",
                            )
                            start_phase = "build"
                            continue
                        logger.info(f"✅ Coverage targets met:\n{cov_status}")
                    else:
                        logger.info("⏩ Skipping coverage enforcement as requested.")

                    save_state(
                        project_name,
                        i,
                        iteration_output,
                        additional_context,
                        phase="review",
                    )
                    start_phase = "review"

                # Phase 4: Review
                if start_phase == "review":
                    # Check budget before agent call
                    budget = check_budget(budget)

                    logger.info(
                        f"🔎 [RALPH LOOP] [PHASE: review] (Iteration {i}/{MAX_ITERATIONS})"
                    )
                    if review:
                        review_output, review_passed = run_review_logic(
                            agent, prd_file, caffeinate=caffeinate, stream=stream
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
                commit_output, _ = run_agent(
                    commit_cmd, caffeinate=caffeinate, stream=stream
                )
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
                    main_branch = get_main_branch()
                    logger.info(f"Merging {branch_name} into {main_branch}...")
                    _switch_to_main()
                    run_command(["git", "merge", branch_name])
                else:
                    logger.info(
                        f"Auto-merge is OFF. Changes remain on branch {branch_name}."
                    )
                    _switch_to_main()

                mark_prd_completed(project_name)
            else:
                logger.error(
                    f"FAILED: Did not find completion promise within {MAX_ITERATIONS} iterations."
                )
                sys.exit(1)

    finally:
        main_branch = get_main_branch()
        logger.info(
            f"Ralph Loop process complete. Returning to '{main_branch}' branch..."
        )
        _switch_to_main()

    print("All PRDs processed successfully.")
