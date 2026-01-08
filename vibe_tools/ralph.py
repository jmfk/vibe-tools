"""
Core engine for the modular project lifecycle.
Includes the Planner Agent, Reconciliation Loops, and Implementation Loop.
"""

import pathlib
from typing import List

import yaml

from typing import Callable, Optional

from vibe_tools.cost import AGENT_DEFAULT_MODEL, CostLogger
from vibe_tools.utils import (
    ARCHITECTURE,
    ARCHITECTURE_SPEC,
    BUILD,
    BUILD_CURRENT,
    CICD_SPEC,
    INFRA_SPEC,
    PRD_DIR,
    TESTING_SPEC,
    check_plan_dependencies,
    collect_prd_files,
    get_agent_command,
    get_automerge_branch,
    get_file_hash,
    get_main_branch,
    get_prompt,
    is_dirty,
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
    ):
        self.name = name
        self.desired_file = desired_file
        self.current_file = current_file
        self.agent = agent
        self.stream = stream
        self.caffeinate = caffeinate
        self.instructions = []

        config = load_config()
        if config.get("ralph", {}).get("auto_merge", False):
            self.branch_name = branch_name or get_automerge_branch(config)
        else:
            self.branch_name = branch_name or f"vibe/{name.lower().replace(' ', '_')}"

    def run(self) -> bool:
        """Executes the reconciliation loop."""
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
        output, code = run_agent(cmd, caffeinate=self.caffeinate, stream=self.stream)

        if code == 0 and COMPLETION_PROMISE in output:
            log_success(self.name, "Reconciliation successful.")
            logger.info(f"✅ {self.name} reconciliation successful.")

            # Commit changes if dirty
            if is_dirty():
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
                log_issue(self.name, iteration, self.max_iterations, f"Prompt build error: {e}")
                return False

            # Call LLM directly (no agent wrapper)
            try:
                llm_output = run_llm(prompt, model=self.model, debug=self.debug)
                logger.debug(f"LLM output (iteration {iteration}): {llm_output[:500]}...")
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
    """Analyzes PRDs and updates project-state.json with plans."""
    prds = collect_prd_files()
    if not prds:
        logger.warning("No PRDs found in project/prds/ to generate plan.")
        return False

    state = load_project_state()
    config = load_config()

    # Determine the starting point for the lineage
    auto_merge = config.get("ralph", {}).get("auto_merge", False)
    if auto_merge:
        base_branch = get_automerge_branch(config)
    else:
        base_branch = get_main_branch()

    # Track lineage and find parent branch
    last_completed_branch = base_branch
    completed_plans = [
        p_id
        for p_id, p_info in state["plans"].items()
        if p_info.get("status") == "completed"
    ]
    if completed_plans:
        # Sort by creation time if we had it, but for now we'll assume alphabetical order of PRDs if not specified
        # or use the order in state["plans"] which is usually the implementation order.
        last_plan_id = completed_plans[-1]
        last_completed_branch = f"feature/{last_plan_id}"

    for prd_path in prds:
        prd_id = prd_path.stem
        if auto_merge:
            branch_name = get_automerge_branch(config)
        else:
            branch_name = f"feature/{prd_id}"

        # Ensure it's in state["plans"]
        if prd_id not in state["plans"]:
            state["plans"][prd_id] = {
                "status": "pending",
                "depends_on": [],
                "title": prd_id.replace("prd_", "").replace("_", " ").title(),
                "file": str(prd_path),
                "is_direct_prd": True,
                "branch": branch_name,
                "parent_branch": last_completed_branch,
            }
            state["branch_lineage"][branch_name] = last_completed_branch
        else:
            # Update file path and ensure branch/parent_branch exist
            state["plans"][prd_id]["file"] = str(prd_path)
            state["plans"][prd_id]["is_direct_prd"] = True

            # Always update branch if auto_merge is true, or if branch is missing
            if auto_merge or "branch" not in state["plans"][prd_id]:
                state["plans"][prd_id]["branch"] = branch_name

            if "parent_branch" not in state["plans"][prd_id]:
                # If it's already in state but missing parent_branch, try to find it
                # or default to main
                state["plans"][prd_id]["parent_branch"] = state["branch_lineage"].get(
                    branch_name, get_main_branch()
                )

        # Update last_completed_branch for the next one in the loop if we want strict linear
        # (Though we might want to only update it if the previous one was just added or is completed)
        # For initialization, we'll assume linear based on the collected PRD order.
        last_completed_branch = branch_name

    save_project_state(state)

    logger.info("✅ Updated project state with plans from PRDs.")
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

        if tests_passed:
            log_success("debug_loop", f"Targets {', '.join(targets)} passed!")
            return True

        summary = tester.get_summary(failed_targets)
        log_issue("debug_loop", i, iterations, summary)
        logger.warning(f"❌ Targets failed. Asking {agent} to fix...")

        try:
            prompt_template = get_prompt("test_fix_prompt.txt")
        except FileNotFoundError as e:
            logger.error(f"Error: {e}")
            return False

        prompt = prompt_template.format(test_output=test_output)
        cmd = get_agent_command(agent, prompt)
        agent_output, _ = run_agent(cmd, stream=stream)

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
        logger.error(f"❌ No plans or PRDs found.")
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

    logger.info("📍 Starting Implementation Phase")

    for plan_id, plan_info in plans_to_run.items():
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
        if not plan_file_str:
            # If path missing, try fallback to PRD_DIR
            plan_file_path = PRD_DIR / f"{plan_id}.yaml"
            if not plan_file_path.is_file():
                logger.error(
                    f"Plan {plan_id} has no file path and fallback {plan_file_path} not found. Skipping."
                )
                continue
        else:
            plan_file_path = pathlib.Path(plan_file_str)
            if not plan_file_path.is_file():
                # Try fallback to PRD_DIR
                fallback_path = PRD_DIR / f"{plan_id}.yaml"
                if fallback_path.is_file():
                    plan_file_path = fallback_path
                else:
                    logger.error(
                        f"Plan file {plan_file_path} not found and no fallback in {PRD_DIR}. Skipping."
                    )
                    continue

        plan_yaml_path = plan_file_path

        if not plan_yaml_path.is_file():
            logger.error(
                f"Normalized plan {plan_yaml_path} not found or is not a file. Skipping."
            )
            continue

        try:
            plan_data = yaml.safe_load(plan_yaml_path.read_text())
        except Exception as e:
            logger.error(f"Failed to parse {plan_yaml_path}: {e}")
            continue

        if plan_data is None:
            plan_data = {}

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
        _switch_to_branch(
            branch_name, agent, plan_id, parent_branch=parent_branch, stream=stream
        )

        success = False
        for i in range(1, max_impl_iterations + 1):
            logger.info(f"🛠️ [IMPLEMENTATION] Iteration {i}/{max_impl_iterations}")

            # 1. Implementation
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
            output, code = run_agent(cmd, stream=stream)

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
                run_command(["git", "add", "."], check=False)
                run_command(
                    [
                        "git",
                        "commit",
                        "-m",
                        f"vibe: implementation iteration {i} for plan '{plan_id}'",
                    ],
                    check=False,
                )

            # 2. Quality Gates
            logger.info("🧪 Running Quality Gates...")
            passed_gates = True

            if tests:
                from vibe_tools.testing import ProjectTester

                tester = ProjectTester()

                be_targets = [t for t in test_targets if tester.is_backend_target(t)]
                fe_targets = [t for t in test_targets if tester.is_frontend_target(t)]

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

            # Build step: verify build system works and software can start in dev environment
            if passed_gates and BUILD.exists():
                logger.info("🔨 Running Build Verification...")
                build_loop = RalphLoop(
                    name="Build",
                    desired_file=BUILD,
                    current_file=BUILD_CURRENT,
                    agent=agent,
                    stream=stream,
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

            if passed_gates and review:
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
                review_output, _ = run_agent(review_cmd, stream=stream)
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
            run_agent(commit_cmd, stream=stream)

            # Update status in project-state.json
            state = load_project_state()
            if plan_id not in state["plans"]:
                state["plans"][plan_id] = {}
            state["plans"][plan_id]["status"] = "completed"

            # Mark in completed_prds
            if plan_id not in state.get("completed_prds", []):
                state["completed_prds"].append(plan_id)

            save_project_state(state)

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
            return False

    return True


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
        run_agent(cmd, caffeinate=caffeinate, stream=stream)

        # Final attempt after agent fix
        final_output, final_code = run_command(
            ["git", "checkout", branch_name], check=False
        )
        if final_code != 0:
            logger.error(
                f"Agent was unable to resolve git conflict. Final error: {final_output}"
            )
            import sys

            sys.exit(1)
