"""
Core engine for the modular project lifecycle.
Includes the Planner Agent, Reconciliation Loops, and Implementation Loop.
"""

import datetime
import pathlib
import sys
from typing import Callable, List

import yaml

from vibe_tools import utils
from vibe_tools.cost import AGENT_DEFAULT_MODEL, CostLogger
from vibe_tools.issues import FAILS_DIR, Issue, IssueBody, save_issue, generate_issue_id, BACKLOG_DIR, HISTORY_DIR
from vibe_tools.utils import (
    ARCHITECTURE_SPEC,
    DEV_ENV,
    DEV_ENV_CURRENT,
    CICD_SPEC,
    INFRA_SPEC,
    PRD_DIR,
    PRD_DONE_DIR,
    PRD_FAILED_DIR,
    PRD_PROCESSING_DIR,
    TESTING_SPEC,
    PLANNING_BACKLOG_DIR,
    PLANNING_DIR,
    PLANNING_HISTORY_DIR,
    PLANNING_INBOX_DIR,
    PLANNING_REJECTED_DIR,
    check_plan_dependencies,
    collect_prd_files,
    commit_and_register_phase,
    get_agent_command,
    get_automerge_branch,
    get_changed_files,
    get_file_hash,
    get_main_branch,
    get_prompt,
    is_dirty,
    is_phase_completed,
    load_config,
    load_project_state,
    log_issue,
    log_start,
    log_success,
    logger,
    run_agent,
    run_command,
    run_llm,
    save_project_state,
    switch_to_main,
    safe_yaml_load,
    safe_yaml_dump,
    update_state_phase,
    parse_prd_filename,
    update_md_implementation_status,
)

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
        branch_name: str = None,
        prd_path: pathlib.Path = None,
        phase_id: str = None,
    ):
        self.name = name
        self.desired_file = desired_file
        self.current_file = current_file
        self.agent = agent
        self.stream = stream
        self.caffeinate = caffeinate
        self.instructions = []
        self.prd_path = prd_path
        self.phase_id = phase_id

        config = load_config()
        if config.get("ralph", {}).get("auto_merge", False):
            self.branch_name = branch_name or get_automerge_branch(config)
        else:
            self.branch_name = branch_name or f"vibe/{name.lower().replace(' ', '_')}"

    def run(self) -> bool:
        """Executes the reconciliation loop."""
        from vibe_tools.utils import is_phase_completed, commit_and_register_phase

        if self.prd_path and self.phase_id:
            if is_phase_completed(self.prd_path, self.phase_id):
                logger.info(
                    f"⏭️ Phase '{self.phase_id}' already completed for {self.name}. Skipping."
                )
                return True

        log_start(
            self.name,
            f"Reconciling {self.desired_file.name} vs {self.current_file.name}",
        )
        logger.info(f"🔄 Starting {self.name} Loop...")

        # Switch to the dedicated branch before starting
        _switch_to_branch(self.branch_name, self.agent, self.name, stream=self.stream)

        if not self.desired_file.exists():
            logger.error(f"❌ Desired file {self.desired_file} not found.")
            # Check if there's a corresponding .md spec that needs normalization
            if self.name.lower() == "architecture setup" and ARCHITECTURE_SPEC.exists():
                logger.info(
                    f"💡 Found {ARCHITECTURE_SPEC}. Run 'vibe normalize' first."
                )
            elif self.name.lower() == "infrastructure" and INFRA_SPEC.exists():
                logger.info(f"💡 Found {INFRA_SPEC}. Run 'vibe normalize' first.")
            elif self.name.lower() == "ci/cd" and CICD_SPEC.exists():
                logger.info(f"💡 Found {CICD_SPEC}. Run 'vibe normalize' first.")
            elif self.name.lower() == "testing" and TESTING_SPEC.exists():
                logger.info(f"💡 Found {TESTING_SPEC}. Run 'vibe normalize' first.")
            return False

        # 1. Compare Desired vs Current
        desired_content = self.desired_file.read_text()
        current_content = (
            self.current_file.read_text() if self.current_file.exists() else None
        )

        # Sync Check
        if current_content and get_file_hash(self.desired_file) == get_file_hash(
            self.current_file
        ):
            logger.info(f"✅ {self.name} is already in sync.")
            if self.prd_path and self.phase_id:
                from vibe_tools.utils import update_state_phase

                update_state_phase(self.prd_path, self.phase_id, status="completed")
            return True

        mode = "MIGRATION" if current_content else "INITIALIZATION"
        if not current_content:
            current_content = "NOT FOUND"

        logger.info(f"📍 Mode: {mode}")

        # 2. Prepare prompt
        try:
            prompt_template = get_prompt("reconciliation_prompt.txt")
        except FileNotFoundError as e:
            logger.error(f"Error: {e}")
            return False

        custom_instructions = ""
        if self.instructions:
            for idx, inst in enumerate(self.instructions, 1):
                custom_instructions += f"{idx}. {inst}\n"

        prompt = prompt_template.format(
            name=self.name,
            mode=mode,
            desired_file=self.desired_file.name,
            current_file=self.current_file.name,
            desired_content=desired_content,
            current_content=current_content,
            custom_instructions=custom_instructions,
        )

        # 3. Run Agent
        cmd = get_agent_command(self.agent, prompt)
        if utils.verbose_logger:
            utils.verbose_logger.log_event("prompt", prompt, f"{self.name}_reconciliation")

        output, code = run_agent(cmd, caffeinate=self.caffeinate, stream=self.stream)

        if utils.verbose_logger:
            utils.verbose_logger.log_event("reply", output, f"{self.name}_reconciliation")

        if code == 0 and COMPLETION_PROMISE in output:
            log_success(self.name, "Reconciliation successful.")
            logger.info(f"✅ {self.name} reconciliation successful.")

            # Commit changes if dirty
            if is_dirty():
                if self.prd_path and self.phase_id:
                    commit_and_register_phase(
                        self.prd_path,
                        self.phase_id,
                        f"vibe: reconciliation step '{self.name}' complete for {self.phase_id}",
                    )
                else:
                    logger.info(f"💾 Committing changes on {self.branch_name}...")
                    run_command(["git", "add", "."], check=False)
                    run_command(
                        [
                            "git",
                            "commit",
                            "-m",
                            f"vibe: reconciliation step '{self.name}' complete",
                        ],
                        check=False,
                    )

            return True
        else:
            log_issue(self.name, 1, 1, "Reconciliation failed or incomplete")
            logger.error(f"❌ {self.name} reconciliation failed or incomplete.")
            return False


class QuickFixLoop:
    """
    Generic quick-fix loop that uses direct LLM calls (no agent wrapper).
    Takes a success function to determine when the fix is complete.
    """

    def __init__(
        self,
        name: str,
        success_fn: Callable[[], bool],
        prompt_builder: Callable[[int], str],
        max_iterations: int = 5,
        model: str = "gemini-3-flash",
        debug: bool = False,
    ):
        """
        Initialize QuickFixLoop.

        Args:
            name: Name of the fix operation (for logging)
            success_fn: Function that returns True if fix succeeded, False otherwise
            prompt_builder: Function that takes iteration number and returns prompt string
            max_iterations: Maximum number of fix attempts
            model: LLM model to use (default: gemini-3-flash)
            debug: Enable debug logging
        """
        self.name = name
        self.success_fn = success_fn
        self.prompt_builder = prompt_builder
        self.max_iterations = max_iterations
        self.model = model
        self.debug = debug

    def run(self) -> bool:
        """
        Execute the quick-fix loop.

        Returns:
            True if fix succeeded within max_iterations, False otherwise
        """
        log_start(self.name, f"Quick fix loop (max {self.max_iterations} iterations)")
        logger.info(f"🔄 Starting {self.name} Quick Fix Loop...")

        # Check if already successful
        if self.success_fn():
            log_success(self.name, "Already successful, no fix needed")
            logger.info(f"✅ {self.name} is already successful.")
            return True

        for iteration in range(1, self.max_iterations + 1):
            logger.info(
                f"🔧 [{self.name}] Fix attempt {iteration}/{self.max_iterations}..."
            )

            # Build prompt for this iteration
            try:
                prompt = self.prompt_builder(iteration)
            except Exception as e:
                logger.error(f"Error building prompt: {e}")
                log_issue(
                    self.name,
                    iteration,
                    self.max_iterations,
                    f"Prompt build error: {e}",
                )
                return False

            # Call LLM directly (no agent wrapper)
            try:
                if utils.verbose_logger:
                    utils.verbose_logger.log_event(
                        "prompt", prompt, f"{self.name}_quickfix_iteration_{iteration}"
                    )

                llm_output = run_llm(prompt, model=self.model, debug=self.debug)

                if utils.verbose_logger:
                    utils.verbose_logger.log_event(
                        "reply",
                        llm_output,
                        f"{self.name}_quickfix_iteration_{iteration}",
                    )

                logger.debug(
                    f"LLM output (iteration {iteration}): {llm_output[:500]}..."
                )
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                log_issue(
                    self.name,
                    iteration,
                    self.max_iterations,
                    f"LLM call error: {e}",
                )
                if iteration < self.max_iterations:
                    continue
                else:
                    return False

            # Check if fix succeeded
            try:
                if self.success_fn():
                    log_success(
                        self.name,
                        f"Fix succeeded after {iteration} iteration(s)",
                    )
                    logger.info(
                        f"✅ {self.name} fix succeeded after {iteration} iteration(s)."
                    )
                    return True
            except Exception as e:
                logger.warning(f"Error checking success: {e}")
                log_issue(
                    self.name,
                    iteration,
                    self.max_iterations,
                    f"Success check error: {e}",
                )

            # Not successful yet
            if iteration < self.max_iterations:
                log_issue(
                    self.name,
                    iteration,
                    self.max_iterations,
                    "Fix attempt did not succeed, retrying...",
                )
                logger.info(f"⚠️  Fix attempt {iteration} did not succeed, retrying...")
            else:
                log_issue(
                    self.name,
                    iteration,
                    self.max_iterations,
                    "Fix failed after all iterations",
                )
                logger.error(
                    f"❌ {self.name} fix failed after {self.max_iterations} iterations."
                )

        return False


def generate_prd_plan() -> bool:
    """Analyzes PRDs and updates state if needed (though mostly derived from filesystem now)."""
    prds = collect_prd_files()
    if not prds:
        logger.warning(
            "No PRDs found in implementation/prds/processing/ to generate plan."
        )
        return False

    state = load_project_state()
    # Plans are derived from filesystem in load_project_state()
    # This function now mostly ensures lineage is tracked in state.json

    config = load_config()
    auto_merge = config.get("ralph", {}).get("auto_merge", False)
    base_branch = get_automerge_branch(config) if auto_merge else get_main_branch()

    last_completed_branch = base_branch
    completed_plans = [
        p_id
        for p_id, p_info in state["plans"].items()
        if p_info.get("status") == "completed"
    ]
    if completed_plans:
        last_plan_id = completed_plans[-1]
        last_completed_branch = f"feature/{last_plan_id}"

    for prd_path in prds:
        prd_id = prd_path.stem
        branch_name = (
            get_automerge_branch(config) if auto_merge else f"feature/{prd_id}"
        )

        if branch_name not in state["branch_lineage"]:
            state["branch_lineage"][branch_name] = last_completed_branch

        last_completed_branch = branch_name

    save_project_state(state)
    logger.info("✅ Updated branch lineage in project state.")
    return True


def debugging_loop(
    agent: str, targets: List[str], stream: bool = False, iterations: int = 5
) -> bool:
    """Runs a set of test targets in a loop until they pass or max iterations reached."""
    from vibe_tools.testing import ProjectTester

    tester = ProjectTester()
    config = load_config()
    cost_logger = CostLogger(config)

    log_start("debug_loop", f"Running targets: {', '.join(targets)}")

    for i in range(1, iterations + 1):
        logger.info(
            f"🧪 [DEBUG LOOP] Running targets: {', '.join(targets)} (Iteration {i}/{iterations})"
        )

        test_output, tests_passed, env_failures, failed_targets = tester.run_tests(
            targets=targets, parallel=False
        )

        if utils.verbose_logger:
            utils.verbose_logger.log_event("test_output", test_output, f"debug_iteration_{i}")

        if tests_passed:
            log_success("debug_loop", f"Targets {', '.join(targets)} passed!")
            return True

        # Check for coverage failure
        if tester.is_coverage_failure(test_output):
            logger.warning(
                "📉 Low coverage detected. Creating an issue and continuing."
            )

            issue_id = generate_issue_id()
            issue = Issue(
                id=issue_id,
                title=f"Improve test coverage for {', '.join(targets)}",
                status="backlog",
                severity="medium",
                service="testing",
                summary=f"Automated coverage check failed for targets: {', '.join(targets)}",
                created_at=datetime.datetime.now().isoformat(),
                updated_at=datetime.datetime.now().isoformat(),
                body=IssueBody(
                    summary=f"The following test targets failed coverage requirements:\n{', '.join(targets)}",
                    evidence=test_output,
                    acceptance_criteria="Reach the required coverage threshold.",
                ),
            )
            save_issue(issue)
            logger.info(f"📄 Created issue {issue_id} to track coverage improvement.")
            # We don't return False here anymore, we let it continue to see if other tests failed
            if tests_passed:
                return True

        # Parse individual failures and re-run to get clean output
        failures = tester.parse_failures(test_output)
        clean_context = []
        if failures:
            logger.info(
                f"🔍 Found {len(failures)} individual test failures. Gathering clean context..."
            )
            for failure in failures:
                single_output, single_passed = tester.run_single_test(failure)
                clean_context.append(
                    f"--- CLEAN OUTPUT FOR TEST: {failure['id']} ---\n{single_output}"
                )

            # Use clean context instead of the noisy full output if we have it
            agent_test_output = "\n\n".join(clean_context)
        else:
            agent_test_output = test_output

        summary = tester.get_summary(failed_targets)
        log_issue("debug_loop", i, iterations, summary)
        logger.warning(f"❌ Targets failed. Asking {agent} to fix...")

        try:
            prompt_template = get_prompt("test_fix_prompt.txt")
        except FileNotFoundError as e:
            logger.error(f"Error: {e}")
            return False

        prompt = prompt_template.format(test_output=agent_test_output)
        cmd = get_agent_command(agent, prompt)

        if utils.verbose_logger:
            utils.verbose_logger.log_event("prompt", prompt, f"debug_iteration_{i}")

        agent_output, _ = run_agent(cmd, stream=stream)

        if utils.verbose_logger:
            utils.verbose_logger.log_event("reply", agent_output, f"debug_iteration_{i}")

        # Log costs

        cost_logger.log_run(
            agent=agent,
            model=AGENT_DEFAULT_MODEL.get(agent, "unknown"),
            prompt=prompt,
            output=agent_output,
            prd_name="N/A",
            iteration=i,
            phase="debug_loop",
            purpose=f"fixing_{'_'.join(targets)}",
        )

        if COMPLETION_PROMISE not in agent_output:
            logger.warning(
                "⏳ Agent did not signal completion with <promise>DONE</promise>. Continuing loop..."
            )

    logger.error(
        f"❌ Failed to fix {', '.join(targets)} after {iterations} iterations."
    )
    return False


def check_automerge_sync(config) -> bool:
    """Verifies that the automerge branch is up to date with the main branch."""
    auto_merge = config.get("ralph", {}).get("auto_merge", False)
    if not auto_merge:
        return True

    import click

    automerge_branch = get_automerge_branch(config)
    main_branch = get_main_branch()

    # Ensure automerge branch exists
    _, code = run_command(
        ["git", "rev-parse", "--verify", automerge_branch], check=False
    )
    if code != 0:
        logger.info(
            f"🌿 Automerge branch '{automerge_branch}' does not exist. It will be created from {main_branch}."
        )
        run_command(["git", "checkout", main_branch], check=False)
        run_command(["git", "checkout", "-b", automerge_branch], check=False)
        return True

    # Check if there are commits in main not in automerge
    stdout, code = run_command(
        ["git", "log", f"{automerge_branch}..{main_branch}", "--oneline"], check=False
    )
    if code == 0 and stdout.strip():
        click.echo(
            click.style(
                f"\n⚠️  The automerge branch '{automerge_branch}' is behind '{main_branch}'.",
                fg="yellow",
                bold=True,
            )
        )
        click.echo(
            f"The following commits are in '{main_branch}' but not in '{automerge_branch}':"
        )
        click.echo(stdout.strip())

        if click.confirm(
            f"\nWould you like to merge '{main_branch}' into '{automerge_branch}' now?",
            default=True,
        ):
            run_command(["git", "checkout", automerge_branch], check=False)
            stdout, code = run_command(["git", "merge", main_branch], check=False)
            if code != 0:
                click.echo(
                    click.style(f"❌ Merge failed with conflicts:\n{stdout}", fg="red")
                )
                return click.confirm(
                    "Proceed anyway with existing conflicts?", default=False
                )
            click.echo(
                click.style(
                    f"✅ Merged '{main_branch}' into '{automerge_branch}'.", fg="green"
                )
            )
            return True
        else:
            return click.confirm(
                "Proceed anyway? (This might cause issues with the branch lineage)",
                default=False,
            )

    return True


def implementation_loop(agent: str, stream: bool = False) -> bool:
    """Executes the implementation phase based on granular YAML plans or direct PRDs from state.json."""
    state = load_project_state()
    plans_to_run = state.get("plans", {})

    if not plans_to_run:
        logger.info(
            "ℹ️ No plans found in state.json. Falling back to direct PRD discovery."
        )
        generate_prd_plan()
        state = load_project_state()
        plans_to_run = state.get("plans", {})

    if not plans_to_run:
        logger.error("❌ No plans or PRDs found.")
        return False

    config = load_config()

    # Check automerge sync before starting
    if not check_automerge_sync(config):
        logger.error("❌ Aborted due to automerge sync failure or user cancellation.")
        return False

    iterations_config = config.get("iterations", {})
    max_impl_iterations = iterations_config.get("implementation", MAX_ITERATIONS)
    # ... rest of the setup ...
    max_debug_iterations = iterations_config.get("debug", 5)

    ralph_config = config.get("ralph", {})
    review = ralph_config.get("review", True)
    tests = ralph_config.get("tests", True)

    # Sort plans by their filename to respect the sequence
    sorted_plan_ids = sorted(
        plans_to_run.keys(),
        key=lambda pid: pathlib.Path(plans_to_run[pid].get("file", pid)).name
    )

    logger.info("📍 Starting Implementation Phase")

    for plan_id in sorted_plan_ids:
        plan_info = plans_to_run[plan_id]
        # Check plan-level status and dependencies
        if plan_info.get("status") == "completed":
            continue

        missing_deps = check_plan_dependencies(plan_id, state)
        if missing_deps:
            logger.warning(
                f"⚠️ Skipping plan {plan_id}: Missing dependencies: {', '.join(missing_deps)}"
            )
            continue

        plan_file_str = plan_info.get("file")
        plan_file_path = None

        if plan_file_str:
            plan_file_path = pathlib.Path(plan_file_str)
            if not plan_file_path.is_file():
                plan_file_path = None

        if not plan_file_path:
            # Fallback search order: PRD_PROCESSING_DIR, PRD_DONE_DIR, PRD_FAILED_DIR
            fallbacks = [
                PRD_PROCESSING_DIR / f"{plan_id}.yaml",
                PRD_DONE_DIR / f"{plan_id}.yaml",
                PRD_FAILED_DIR / f"{plan_id}.yaml",
                PRD_DIR / f"{plan_id}.yaml",
            ]
            for fb in fallbacks:
                if fb.is_file():
                    plan_file_path = fb
                    logger.info(f"📍 Found plan {plan_id} at {fb}.")
                    break

            if not plan_file_path:
                logger.error(f"❌ Plan file for {plan_id} not found. Skipping.")
                continue

        plan_yaml_path = plan_file_path

        if not plan_yaml_path.is_file():
            logger.error(
                f"Normalized plan {plan_yaml_path} not found or is not a file. Skipping."
            )
            continue

        try:
            plan_data = safe_yaml_load(plan_yaml_path.read_text())
        except Exception as e:
            logger.error(f"Failed to parse {plan_yaml_path}: {e}")
            continue

        if plan_data is None:
            plan_data = {}

        # RESCHEDULING LOGIC
        dependencies = plan_data.get("DEPENDS_ON", [])
        plan_filename = plan_yaml_path.name
        parsed_current = parse_prd_filename(plan_filename)
        
        if parsed_current["format"] == "versioned":
            max_later_dep_seq = 0
            later_dep_id = None
            
            # Check if any dependencies are later in the backlog
            current_idx = sorted_plan_ids.index(plan_id)
            for later_plan_id in sorted_plan_ids[current_idx + 1:]:
                # If this later plan is a dependency of the current one
                if later_plan_id in dependencies or later_plan_id.replace("prd_", "") in dependencies:
                    later_info = plans_to_run[later_plan_id]
                    later_filename = pathlib.Path(later_info["file"]).name
                    parsed_later = parse_prd_filename(later_filename)
                    if parsed_later["sequence"]:
                        if parsed_later["sequence"] > max_later_dep_seq:
                            max_later_dep_seq = parsed_later["sequence"]
                            later_dep_id = later_plan_id

            if later_dep_id:
                import shutil
                # Dependency found LATER in the queue! We must reschedule.
                new_seq = max_later_dep_seq + 5
                version = parsed_current["version"]
                clean_name = parsed_current["name"]
                new_filename = f"v{version}-{new_seq:03d}_{clean_name}.yaml"
                new_path = plan_yaml_path.parent / new_filename
                
                logger.warning(
                    f"🔄 Rescheduling {plan_id} (seq {parsed_current['sequence']}) "
                    f"because it depends on {later_dep_id} (seq {max_later_dep_seq}). "
                    f"New sequence: {new_seq}"
                )
                
                # Rename the file
                shutil.move(str(plan_yaml_path), str(new_path))
                
                # Update MD frontmatter
                md_path_str = plan_info.get("md_path")
                if md_path_str:
                    update_md_implementation_status(
                        pathlib.Path(md_path_str),
                        version,
                        new_seq,
                        new_path
                    )
                
                # Reload state and restart the implementation loop to reflect changes
                logger.info("♻️ Restarting implementation loop after rescheduling...")
                return implementation_loop(agent, stream=stream)

        title = plan_info.get(
            "title", plan_id.replace("prd_", "").replace("_", " ").title()
        )
        description = plan_yaml_path.read_text()

        # Determine branch and parent
        auto_merge = config.get("ralph", {}).get("auto_merge", False)
        if auto_merge:
            branch_name = get_automerge_branch(config)
        else:
            branch_name = plan_info.get("branch", f"feature/{plan_id}")

        parent_branch = plan_info.get("parent_branch", get_main_branch())

        # Extract success criteria
        capabilities = plan_data.get("CAPABILITIES", {})
        success_criteria = []

        if isinstance(capabilities, dict):
            if isinstance(capabilities.get("interaction_mechanisms"), list):
                success_criteria.extend(capabilities["interaction_mechanisms"])
            if isinstance(capabilities.get("patterns"), list):
                success_criteria.extend(capabilities["patterns"])
            if isinstance(capabilities.get("routing"), list):
                success_criteria.extend(capabilities["routing"])
        elif isinstance(capabilities, list):
            success_criteria.extend(capabilities)
        elif isinstance(capabilities, str):
            success_criteria.append(capabilities)

        if not success_criteria:
            success_criteria = ["Implement all capabilities defined in the PRD."]
        test_targets = ["test"]

        logger.info(f"🚀 Executing Plan: {title} ({plan_id})")
        log_start("implement", f"Plan: {title} ({plan_id})")

        # Status is now derived from file location.
        # Plan is already in PRD_PROCESSING_DIR if we are here.

        _switch_to_branch(
            branch_name, agent, plan_id, parent_branch=parent_branch, stream=stream
        )

        success = False
        for i in range(1, max_impl_iterations + 1):
            logger.info(f"🛠️ [IMPLEMENTATION] Iteration {i}/{max_impl_iterations}")

            # 1. Implementation
            impl_phase_id = f"implementation_iteration_{i}"
            if not is_phase_completed(plan_yaml_path, impl_phase_id):
                try:
                    prompt_template = get_prompt("implementation_prompt.txt")
                except FileNotFoundError as e:
                    logger.error(f"Error: {e}")
                    return False

                prompt = prompt_template.format(
                    title=title,
                    description=description,
                    success_criteria=chr(10).join(
                        ["- " + str(c) for c in success_criteria]
                    ),
                )
                cmd = get_agent_command(agent, prompt)

                if utils.verbose_logger:
                    utils.verbose_logger.log_event(
                        "prompt", prompt, f"{plan_id}_iteration_{i}"
                    )

                output, code = run_agent(cmd, stream=stream)

                if utils.verbose_logger:
                    utils.verbose_logger.log_event(
                        "reply", output, f"{plan_id}_iteration_{i}"
                    )

                if code != 0 or COMPLETION_PROMISE not in output:
                    if code != 0:
                        log_issue(
                            "implement",
                            i,
                            max_impl_iterations,
                            f"Agent failed with exit code {code}",
                        )
                    else:
                        log_issue(
                            "implement",
                            i,
                            max_impl_iterations,
                            "Agent did not provide completion promise",
                        )
                    logger.warning(f"⏳ Implementation in progress for {plan_id}...")
                    continue

                # Commit iteration changes if dirty
                if is_dirty():
                    logger.info(
                        f"💾 Committing iteration {i} changes for {plan_id} on {branch_name}..."
                    )
                    commit_and_register_phase(
                        plan_yaml_path,
                        impl_phase_id,
                        f"vibe: implementation iteration {i} for plan '{plan_id}'",
                    )
                else:
                    update_state_phase(
                        plan_yaml_path, impl_phase_id, status="completed"
                    )
            else:
                logger.info(f"⏭️ Phase '{impl_phase_id}' already completed. Skipping.")

            # 2. Quality Gates
            logger.info("🧪 Running Quality Gates...")
            passed_gates = True

            if tests:
                tests_phase_id = f"tests_iteration_{i}"
                if not is_phase_completed(plan_yaml_path, tests_phase_id):
                    from vibe_tools.testing import ProjectTester

                    tester = ProjectTester()

                    be_targets = [
                        t for t in test_targets if tester.is_backend_target(t)
                    ]
                    fe_targets = [
                        t for t in test_targets if tester.is_frontend_target(t)
                    ]

                    # Run Backend Debug Loop
                    if be_targets:
                        logger.info(
                            f"🧬 Starting Backend Debug Loop for: {', '.join(be_targets)}"
                        )
                        if not debugging_loop(
                            agent,
                            be_targets,
                            stream=stream,
                            iterations=max_debug_iterations,
                        ):
                            passed_gates = False

                    # Run Frontend Debug Loop
                    if passed_gates and fe_targets:
                        logger.info(
                            f"🎨 Starting Frontend Debug Loop for: {', '.join(fe_targets)}"
                        )
                        if not debugging_loop(
                            agent,
                            fe_targets,
                            stream=stream,
                            iterations=max_debug_iterations,
                        ):
                            passed_gates = False

                    if passed_gates:
                        if is_dirty():
                            commit_and_register_phase(
                                plan_yaml_path,
                                tests_phase_id,
                                f"vibe: tests passed for iteration {i} of plan '{plan_id}'",
                            )
                        else:
                            update_state_phase(
                                plan_yaml_path, tests_phase_id, status="completed"
                            )
                else:
                    logger.info(
                        f"⏭️ Phase '{tests_phase_id}' already completed. Skipping."
                    )

            # Build step: verify build system works and software can start in dev environment
            if passed_gates and DEV_ENV.exists():
                build_phase_id = f"build_iteration_{i}"
                if not is_phase_completed(plan_yaml_path, build_phase_id):
                    logger.info("🔨 Running Build Verification...")
                    build_loop = RalphLoop(
                        name="Build",
                        desired_file=DEV_ENV,
                        current_file=DEV_ENV_CURRENT,
                        agent=agent,
                        stream=stream,
                        prd_path=plan_yaml_path,
                        phase_id=build_phase_id,
                    )
                    build_loop.instructions = [
                        "Ensure the build system successfully builds all application parts.",
                        "Verify that the built software can be started in the development environment.",
                        "Check that all build dependencies are correctly configured.",
                        "Ensure build artifacts are generated correctly.",
                    ]
                    if not build_loop.run():
                        log_issue(
                            "implement_build",
                            i,
                            max_impl_iterations,
                            "Build verification failed",
                        )
                        logger.error("❌ Build verification failed.")
                        passed_gates = False
                else:
                    logger.info(
                        f"⏭️ Phase '{build_phase_id}' already completed. Skipping."
                    )

            if passed_gates and review:
                review_phase_id = f"review_iteration_{i}"
                if not is_phase_completed(plan_yaml_path, review_phase_id):
                    logger.info("🔎 Running Agentic Review...")
                    try:
                        review_prompt_template = get_prompt(
                            "implementation_review_prompt.txt"
                        )
                    except FileNotFoundError as e:
                        logger.error(f"Error: {e}")
                        return False

                    review_prompt = review_prompt_template.format(
                        title=title,
                        description=description,
                        success_criteria=chr(10).join(
                            ["- " + str(c) for c in success_criteria]
                        ),
                    )
                    review_cmd = get_agent_command(agent, review_prompt)

                    if utils.verbose_logger:
                        utils.verbose_logger.log_event(
                            "prompt", review_prompt, f"{plan_id}_review_iteration_{i}"
                        )

                    review_output, _ = run_agent(review_cmd, stream=stream)

                    if utils.verbose_logger:
                        utils.verbose_logger.log_event(
                            "reply", review_output, f"{plan_id}_review_iteration_{i}"
                        )

                    if "<review>PASSED</review>" not in review_output:
                        log_issue(
                            "implement_review",
                            i,
                            max_impl_iterations,
                            "Agentic review failed",
                        )
                        logger.error("❌ Agentic review failed.")
                        passed_gates = False

                    if passed_gates:
                        if is_dirty():
                            commit_and_register_phase(
                                plan_yaml_path,
                                review_phase_id,
                                f"vibe: agentic review passed for iteration {i} of plan '{plan_id}'",
                            )
                        else:
                            update_state_phase(
                                plan_yaml_path, review_phase_id, status="completed"
                            )
                else:
                    logger.info(
                        f"⏭️ Phase '{review_phase_id}' already completed. Skipping."
                    )

            if passed_gates:
                success = True
                break
            else:
                logger.info("🔄 Retrying implementation to fix quality issues...")

        if success:
            log_success("implement", f"Plan {plan_id} completed successfully.")
            logger.info(f"✅ Plan {plan_id} completed successfully.")

            # Commit any final adjustments from debug loops or review
            if is_dirty():
                logger.info(f"💾 Committing final adjustments for {plan_id}...")
                run_command(["git", "add", "."], check=False)
                run_command(
                    [
                        "git",
                        "commit",
                        "-m",
                        f"vibe: final adjustments for plan '{plan_id}'",
                    ],
                    check=False,
                )

            # Commit changes via agent
            commit_prompt = f"Commit changes for plan: {title}. Ensure all success criteria were met."
            commit_cmd = get_agent_command(agent, commit_prompt)

            if utils.verbose_logger:
                utils.verbose_logger.log_event("prompt", commit_prompt, f"{plan_id}_commit")

            commit_output, _ = run_agent(commit_cmd, stream=stream)

            if utils.verbose_logger:
                utils.verbose_logger.log_event("reply", commit_output, f"{plan_id}_commit")

            # Update status by moving file to done directory
            if plan_file_path.parent != PRD_DONE_DIR:
                target_path = PRD_DONE_DIR / plan_file_path.name
                if not target_path.exists():
                    logger.info(f"📦 Moving {plan_file_path.name} to done.")
                    import shutil

                    shutil.move(str(plan_file_path), str(target_path))

            # Move corresponding MD file to history if it exists
            md_path_str = plan_info.get("md_path")
            if md_path_str:
                md_path = pathlib.Path(md_path_str)
                if md_path.exists() and PLANNING_HISTORY_DIR not in md_path.parents:
                    # Maintain relative directory structure
                    if PLANNING_BACKLOG_DIR in md_path.parents:
                        rel_dir = md_path.parent.relative_to(PLANNING_BACKLOG_DIR)
                    elif PLANNING_INBOX_DIR in md_path.parents:
                        rel_dir = md_path.parent.relative_to(PLANNING_INBOX_DIR)
                    else:
                        rel_dir = md_path.parent.relative_to(PLANNING_DIR)

                    target_md_dir = PLANNING_HISTORY_DIR / rel_dir
                    target_md_dir.mkdir(parents=True, exist_ok=True)
                    target_md_path = target_md_dir / md_path.name
                    logger.info(f"📦 Moving {md_path.name} to history.")
                    import shutil

                    shutil.move(str(md_path), str(target_md_path))

            # Auto-merge if enabled
            auto_merge = config.get("ralph", {}).get("auto_merge", False)
            if auto_merge:
                automerge_branch = get_automerge_branch(config)
                main_branch = get_main_branch()

                if automerge_branch == main_branch:
                    logger.warning(
                        f"⚠️  Automerge branch is set to '{main_branch}'. Skipping automated merge to protect main."
                    )
                    switch_to_main()
                elif branch_name == automerge_branch:
                    logger.info(
                        f"✅ Already on automerge branch '{automerge_branch}'. Skipping redundant merge."
                    )
                    switch_to_main()
                else:
                    logger.info(
                        f"🔄 Auto-merging {branch_name} into {automerge_branch}..."
                    )

                    # Ensure automerge branch exists
                    _, code = run_command(
                        ["git", "rev-parse", "--verify", automerge_branch], check=False
                    )
                    if code != 0:
                        logger.info(
                            f"🌿 Creating automerge branch '{automerge_branch}' from {main_branch}"
                        )
                        run_command(["git", "checkout", main_branch], check=False)
                        run_command(
                            ["git", "checkout", "-b", automerge_branch], check=False
                        )
                        # Switch back to the feature branch for the merge tool to work as expected
                        run_command(["git", "checkout", branch_name], check=False)

                    from vibe_tools.branches import merge_branches

                    merge_branches(branch_name, automerge_branch)

                    # After merge, we should be on automerge_branch. Switch back to main for next plan.
                    switch_to_main()
            else:
                # Switch back to main
                switch_to_main()
        else:
            logger.error(
                f"❌ Failed to complete plan {plan_id} after {max_impl_iterations} iterations."
            )
            # Move file to failed directory
            if plan_file_path.parent != PRD_FAILED_DIR:
                target_path = PRD_FAILED_DIR / plan_file_path.name
                if not target_path.exists():
                    logger.info(f"📦 Moving {plan_file_path.name} to failed.")
                    import shutil

                    shutil.move(str(plan_file_path), str(target_path))

            # Move corresponding MD file to rejected if it exists
            md_path_str = plan_info.get("md_path")
            if md_path_str:
                md_path = pathlib.Path(md_path_str)
                if md_path.exists() and PLANNING_REJECTED_DIR not in md_path.parents:
                    # Maintain relative directory structure
                    if PLANNING_BACKLOG_DIR in md_path.parents:
                        rel_dir = md_path.parent.relative_to(PLANNING_BACKLOG_DIR)
                    elif PLANNING_INBOX_DIR in md_path.parents:
                        rel_dir = md_path.parent.relative_to(PLANNING_INBOX_DIR)
                    else:
                        rel_dir = md_path.parent.relative_to(PLANNING_DIR)

                    target_md_dir = PLANNING_REJECTED_DIR / rel_dir
                    target_md_dir.mkdir(parents=True, exist_ok=True)
                    target_md_path = target_md_dir / md_path.name
                    logger.info(f"📦 Moving {md_path.name} to rejected.")
                    import shutil

                    shutil.move(str(md_path), str(target_md_path))
            return False

    return True


def issue_solve_loop(issue: Issue, agent: str, stream: bool = False) -> bool:
    """Executes the implementation loop for a specific issue."""
    config = load_config()

    # Check automerge sync before starting
    if not check_automerge_sync(config):
        logger.error("❌ Aborted due to automerge sync failure or user cancellation.")
        return False

    iterations_config = config.get("iterations", {})
    max_impl_iterations = iterations_config.get("implementation", MAX_ITERATIONS)
    max_debug_iterations = iterations_config.get("debug", 5)

    ralph_config = config.get("ralph", {})
    review = ralph_config.get("review", True)
    tests = ralph_config.get("tests", True)

    branch_name = f"issue/{issue.id}"

    # Determine parent branch (use automerge branch if enabled)
    # This ensures that sequential issues in a batch see each other's changes.
    auto_merge = ralph_config.get("auto_merge", False)
    if auto_merge:
        parent_branch = get_automerge_branch(config)
    else:
        parent_branch = get_main_branch()

    logger.info(f"🚀 Solving Issue: {issue.title} ({issue.id})")
    log_start("issue_solve", f"Issue: {issue.title} ({issue.id})")
    _switch_to_branch(
        branch_name, agent, issue.id, parent_branch=parent_branch, stream=stream
    )

    # Determine issue file path for phase tracking
    issue_file_path = BACKLOG_DIR / f"{issue.id}.md"
    if not issue_file_path.exists():
        issue_file_path = HISTORY_DIR / f"{issue.id}.md"

    history = []
    success = False

    for i in range(1, max_impl_iterations + 1):
        logger.info(f"🛠️ [ISSUE SOLVE] Iteration {i}/{max_impl_iterations}")
        iteration_data = {"iteration": i, "outcome": "failed", "details": ""}

        # 1. Implementation
        impl_phase_id = f"issue_implementation_iteration_{i}"
        if not is_phase_completed(issue_file_path, impl_phase_id):
            try:
                prompt_template = get_prompt("issue_solve_prompt.txt")
            except FileNotFoundError as e:
                logger.error(f"Error: {e}")
                return False

            prompt = prompt_template.format(
                issue_id=issue.id,
                issue_title=issue.title,
                issue_body=issue.body.to_markdown(),
            )
            cmd = get_agent_command(agent, prompt)

            if utils.verbose_logger:
                utils.verbose_logger.log_event("prompt", prompt, f"{issue.id}_iteration_{i}")

            output, code = run_agent(cmd, stream=stream)

            if utils.verbose_logger:
                utils.verbose_logger.log_event("reply", output, f"{issue.id}_iteration_{i}")

            if code != 0 or COMPLETION_PROMISE not in output:
                reason = (
                    f"Agent failed with exit code {code}"
                    if code != 0
                    else "Agent did not provide completion promise"
                )
                log_issue("issue_solve", i, max_impl_iterations, reason)
                iteration_data["details"] = reason
                history.append(iteration_data)
                continue

            # Commit iteration changes
            if is_dirty():
                logger.info(f"💾 Committing iteration {i} changes for {issue.id}...")
                commit_and_register_phase(
                    issue_file_path,
                    impl_phase_id,
                    f"vibe: issue solve iteration {i} for {issue.id}",
                )
            else:
                update_state_phase(issue_file_path, impl_phase_id, status="completed")
        else:
            logger.info(f"⏭️ Phase '{impl_phase_id}' already completed. Skipping.")

        # 2. Quality Gates
        passed_gates = True
        gate_details = []

        if tests:
            tests_phase_id = f"issue_tests_iteration_{i}"
            if not is_phase_completed(issue_file_path, tests_phase_id):
                from vibe_tools.testing import ProjectTester

                tester = ProjectTester()
                # For issues, we might want to run all tests or a subset.
                # Defaulting to all 'test' targets for now.
                test_targets = ["test"]

                be_targets = [t for t in test_targets if tester.is_backend_target(t)]
                fe_targets = [t for t in test_targets if tester.is_frontend_target(t)]

                if be_targets:
                    if not debugging_loop(
                        agent,
                        be_targets,
                        stream=stream,
                        iterations=max_debug_iterations,
                    ):
                        passed_gates = False
                        gate_details.append("Backend tests failed")

                if passed_gates and fe_targets:
                    if not debugging_loop(
                        agent,
                        fe_targets,
                        stream=stream,
                        iterations=max_debug_iterations,
                    ):
                        passed_gates = False
                        gate_details.append("Frontend tests failed")

                if passed_gates:
                    if is_dirty():
                        commit_and_register_phase(
                            issue_file_path,
                            tests_phase_id,
                            f"vibe: tests passed for iteration {i} of issue '{issue.id}'",
                        )
                    else:
                        update_state_phase(
                            issue_file_path, tests_phase_id, status="completed"
                        )
            else:
                logger.info(f"⏭️ Phase '{tests_phase_id}' already completed. Skipping.")

        if passed_gates and review:
            review_phase_id = f"issue_review_iteration_{i}"
            if not is_phase_completed(issue_file_path, review_phase_id):
                try:
                    review_prompt_template = get_prompt(
                        "implementation_review_prompt.txt"
                    )
                    review_prompt = review_prompt_template.format(
                        title=issue.title,
                        description=issue.body.summary,
                        success_criteria=issue.body.acceptance_criteria
                        or "Resolve the issue as described.",
                    )
                    review_cmd = get_agent_command(agent, review_prompt)

                    if utils.verbose_logger:
                        utils.verbose_logger.log_event(
                            "prompt", review_prompt, f"{issue.id}_review_iteration_{i}"
                        )

                    review_output, _ = run_agent(review_cmd, stream=stream)

                    if utils.verbose_logger:
                        utils.verbose_logger.log_event(
                            "reply", review_output, f"{issue.id}_review_iteration_{i}"
                        )

                    if "<review>PASSED</review>" not in review_output:
                        passed_gates = False
                        gate_details.append("Agentic review failed")

                    if passed_gates:
                        if is_dirty():
                            commit_and_register_phase(
                                issue_file_path,
                                review_phase_id,
                                f"vibe: agentic review passed for iteration {i} of issue '{issue.id}'",
                            )
                        else:
                            update_state_phase(
                                issue_file_path, review_phase_id, status="completed"
                            )
                except Exception as e:
                    logger.error(f"Review failed: {e}")
                    passed_gates = False
                    gate_details.append(f"Review error: {e}")
            else:
                logger.info(f"⏭️ Phase '{review_phase_id}' already completed. Skipping.")

        if passed_gates:
            success = True
            iteration_data["outcome"] = "success"
            history.append(iteration_data)
            break
        else:
            iteration_data["details"] = "; ".join(gate_details)
            history.append(iteration_data)
            logger.info("🔄 Retrying issue solve to fix quality issues...")

    if success:
        log_success("issue_solve", f"Issue {issue.id} solved successfully.")

        # Update status and save locally first so it can be committed
        issue.status = "done"
        issue.updated_at = datetime.datetime.now().isoformat()
        save_issue(issue)

        # Commit final adjustments including the status update
        if is_dirty():
            run_command(["git", "add", "."], check=False)
            run_command(
                [
                    "git",
                    "commit",
                    "-m",
                    f"vibe: final fix and status update for {issue.id}",
                ],
                check=False,
            )

        # Merge if auto_merge is enabled
        if ralph_config.get("auto_merge", False):
            automerge_branch = get_automerge_branch(config)
            from vibe_tools.branches import merge_branches

            merge_branches(branch_name, automerge_branch)
            switch_to_main()
        else:
            switch_to_main()

        return True
    else:
        logger.error(
            f"❌ Failed to solve issue {issue.id} after {max_impl_iterations} iterations."
        )

        # Generate failure report
        attempts_summary = ""
        for h in history:
            attempts_summary += (
                f"- Iteration {h['iteration']}: {h['outcome']}. {h['details']}\n"
            )

        modified_files = "\n".join([f"- {f}" for f in get_changed_files(parent_branch)])

        try:
            report_template = get_prompt("issue_fail_report_template.md")
            report = report_template.format(
                issue_id=issue.id,
                issue_title=issue.title,
                iterations=max_impl_iterations,
                attempts_summary=attempts_summary,
                modified_files=modified_files,
            )

            FAILS_DIR.mkdir(parents=True, exist_ok=True)
            report_path = FAILS_DIR / f"{issue.id}.md"
            report_path.write_text(report)
            logger.info(f"📄 Failure report written to {report_path}")
        except Exception as e:
            logger.error(f"Failed to write failure report: {e}")

        return False


def _switch_to_branch(
    branch_name, agent, project_name, parent_branch=None, caffeinate=False, stream=False
):
    """Robustly switches to a feature branch, using AI rescue if needed."""
    if parent_branch is None:
        parent_branch = get_main_branch()

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

        output, _ = run_agent(cmd, caffeinate=caffeinate, stream=stream)

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
