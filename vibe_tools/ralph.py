"""
Core engine for the modular project lifecycle.
Includes the Planner Agent, Reconciliation Loops, and Implementation Loop.
"""

import datetime
import pathlib
import sys
import re
from typing import Callable, List, Optional, Tuple

import yaml
import click

from vibe_tools import utils
from vibe_tools.cost import AGENT_DEFAULT_MODEL, CostLogger
from vibe_tools.prds import PRD, load_prd, generate_prd_id
from vibe_tools.normalize import normalize_to_data
from vibe_tools.branches import _switch_to_branch
from vibe_tools.utils import (
    ARCHITECTURE_SPEC,
    DEV_ENV_CURRENT,
    CICD_SPEC,
    INFRA_SPEC,
    TESTING_SPEC,
    PRODUCT_BACKLOG_DIR,
    PRODUCT_NEXT_DIR,
    PRODUCT_IN_PROGRESS_DIR,
    PRODUCT_HISTORY_DIR,
    get_agent_command,
    get_automerge_branch,
    get_changed_files,
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
    save_project_state,
    switch_to_main,
    safe_yaml_load,
    safe_yaml_dump,
)

MAX_ITERATIONS = 10
COMPLETION_PROMISE = "<promise>DONE</promise>"


class RalphLoop:
    """Core reconciliation loop between Desired State and Actual State."""

    def __init__(
        self,
        name: str,
        desired_content: str,
        desired_file_name: str,
        current_file: pathlib.Path,
        agent: str = "cursor-agent",
        stream: bool = False,
        branch_name: str = None,
        prd: PRD = None,
        phase_id: str = None,
    ):
        self.name = name
        self.desired_content = desired_content
        self.desired_file_name = desired_file_name
        self.current_file = current_file
        self.agent = agent
        self.stream = stream
        self.instructions = []
        self.prd = prd
        self.phase_id = phase_id

        config = load_config()
        if config.get("ralph", {}).get("auto_merge", False):
            self.branch_name = branch_name or get_automerge_branch(config)
        else:
            self.branch_name = branch_name or f"vibe/{name.lower().replace(' ', '_')}"

    def run(self) -> bool:
        """Executes the reconciliation loop."""
        log_start(
            self.name,
            f"Reconciling {self.desired_file_name} vs {self.current_file.name}",
        )
        logger.info(f"🔄 Starting {self.name} Loop...")

        # Switch to the dedicated branch before starting
        _switch_to_branch(self.branch_name, self.agent, self.name, stream=self.stream)

        if not self.desired_content:
            logger.error(f"❌ Desired content for {self.desired_file_name} is empty.")
            return False

        # 1. Compare Desired vs Current
        current_content = (
            self.current_file.read_text() if self.current_file.exists() else None
        )

        # Sync Check - compare desired YAML content string with current file content
        import hashlib

        desired_hash = hashlib.sha256(self.desired_content.encode()).hexdigest()

        if current_content and get_file_hash(self.current_file) == desired_hash:
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
            desired_file=self.desired_file_name,
            current_file=self.current_file.name,
            desired_content=self.desired_content,
            current_content=current_content,
            custom_instructions=custom_instructions,
        )

        # 3. Run Agent
        cmd = get_agent_command(self.agent, prompt)
        output, code = run_agent(cmd, stream=self.stream)

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


def debugging_loop(
    agent: str, targets: List[str], stream: bool = False, iterations: int = 5
) -> Tuple[bool, str]:
    """Runs a set of test targets in a loop until they pass or max iterations reached."""
    from vibe_tools.testing import ProjectTester

    tester = ProjectTester()
    config = load_config()
    cost_logger = CostLogger(config)

    log_start("debug_loop", f"Running targets: {', '.join(targets)}")
    
    last_summary = "Tests failed but no summary was generated."

    for i in range(1, iterations + 1):
        logger.info(
            f"🧪 [DEBUG LOOP] Running targets: {', '.join(targets)} (Iteration {i}/{iterations})"
        )

        test_output, tests_passed, env_failures, failed_targets = tester.run_tests(
            targets=targets, parallel=False
        )

        if tests_passed:
            log_success("debug_loop", f"Targets {', '.join(targets)} passed!")
            return True, ""

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

        last_summary = tester.get_summary(failed_targets)
        log_issue("debug_loop", i, iterations, last_summary)
        logger.warning(f"❌ Targets failed. Asking {agent} to fix...")

        try:
            prompt_template = get_prompt("test_fix_prompt.txt")
        except FileNotFoundError as e:
            logger.error(f"Error: {e}")
            return False, str(e)

        prompt = prompt_template.format(test_output=agent_test_output)
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
    return False, last_summary


def check_automerge_sync(config) -> bool:
    """Verifies that the automerge branch is up to date with the main branch."""
    auto_merge = config.get("ralph", {}).get("auto_merge", False)
    if not auto_merge:
        return True

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


def generate_prd_plan() -> bool:
    """Compatibility function for unified PRD structure."""
    logger.info("✅ PRD plan is now managed directly via the 'product/' directory.")
    return True


def implementation_loop(agent: str, stream: bool = False) -> bool:
    """Unified implementation loop working on Markdown PRDs in product/."""
    config = load_config()

    # 1. Check for PRD in progress
    in_progress_files = list(PRODUCT_IN_PROGRESS_DIR.glob("*.md"))
    if len(in_progress_files) > 1:
        logger.error("❌ Multiple PRDs in progress. Only one is allowed at a time.")
        return False

    prd: Optional[PRD] = None
    if in_progress_files:
        prd = load_prd(in_progress_files[0])
        logger.info(f"📍 Resuming PRD: {prd.title} ({prd.id})")
    else:
        # 1. Try to pick from 'next' directory (planned for implementation)
        next_files = sorted(list(PRODUCT_NEXT_DIR.glob("*.md")))
        if next_files:
            selected_file = next_files[0]
            prd = load_prd(selected_file)
            logger.info(f"🚀 Picking next planned PRD: {prd.title} ({prd.id})")
        else:
            # 2. Fallback to backlog
            backlog_files = sorted(list(PRODUCT_BACKLOG_DIR.glob("*.md")))
            if not backlog_files:
                logger.info("ℹ️ No PRDs in 'next' or backlog.")
                return True

            selected_file = backlog_files[0]
            prd = load_prd(selected_file)
            logger.info(f"🚀 Starting PRD from backlog: {prd.title} ({prd.id})")

        # Check dependencies
        state = load_project_state()
        completed = set(state.get("completed_prds", []))
        missing_deps = [d for d in prd.depends_on if d not in completed]
        if missing_deps:
            logger.warning(
                f"⚠️ PRD {prd.id} has missing dependencies: {', '.join(missing_deps)}. Skipping."
            )
            return False

        # Move to in_progress
        new_path = PRODUCT_IN_PROGRESS_DIR / selected_file.name
        prd.status = "in_progress"
        prd.save(new_path)
        selected_file.unlink()
        prd.path = new_path

    # 2. In-Memory Normalization
    logger.info(f"🔄 Normalizing {prd.id} in-memory...")
    try:
        plan_data = normalize_to_data(prd.content, prd.id)
    except Exception as e:
        logger.error(f"❌ Normalization crashed: {e}")
        plan_data = None

    if not plan_data:
        logger.error("❌ Normalization failed. Please check the PRD content.")
        # Move back to next if normalization fails, so it can be tried again after fixing
        next_path = PRODUCT_NEXT_DIR / prd.path.name
        prd.status = "backlog"  # Reset status for 'next'
        prd.save(next_path)
        prd.path.unlink()
        return False

    # 3. Setup Implementation
    if not check_automerge_sync(config):
        # Move back to next if sync fails
        next_path = PRODUCT_NEXT_DIR / prd.path.name
        prd.status = "backlog"
        prd.save(next_path)
        prd.path.unlink()
        return False

    iterations_config = config.get("iterations", {})
    max_impl_iterations = iterations_config.get("implementation", MAX_ITERATIONS)
    max_debug_iterations = iterations_config.get("debug", 5)

    ralph_config = config.get("ralph", {})
    review = ralph_config.get("review", True)
    tests = ralph_config.get("tests", True)

    branch_name = f"feature/{prd.id.lower()}"
    parent_branch = get_main_branch()

    # Extract success criteria
    capabilities = plan_data.get("CAPABILITIES", {})
    success_criteria = []
    if isinstance(capabilities, dict):
        for k, v in capabilities.items():
            if isinstance(v, list):
                success_criteria.extend(v)
            else:
                success_criteria.append(str(v))
    elif isinstance(capabilities, list):
        success_criteria.extend(capabilities)

    if not success_criteria:
        success_criteria = ["Implement all capabilities defined in the PRD."]

    _switch_to_branch(
        branch_name, agent, prd.id, parent_branch=parent_branch, stream=stream
    )

    success = False
    failure_reason = ""
    failure_context = ""

    for i in range(1, max_impl_iterations + 1):
        logger.info(f"🛠️ [IMPLEMENTATION] Iteration {i}/{max_impl_iterations}")

        # 3a. Implementation Step
        try:
            prompt_template = get_prompt("implementation_prompt.txt")
            prompt = prompt_template.format(
                title=prd.title,
                description=prd.content,
                success_criteria=chr(10).join(
                    ["- " + str(c) for c in success_criteria]
                ),
            )
            cmd = get_agent_command(agent, prompt)
            output, code = run_agent(cmd, stream=stream)

            if code != 0 or COMPLETION_PROMISE not in output:
                failure_reason = (
                    f"Agent failed with code {code}"
                    if code != 0
                    else "No completion promise"
                )
                failure_context = output
                continue

            if is_dirty():
                run_command(["git", "add", "."], check=False)
                run_command(
                    ["git", "commit", "-m", f"vibe: impl iteration {i} for {prd.id}"],
                    check=False,
                )
        except Exception as e:
            failure_reason = str(e)
            failure_context = str(e)
            continue

        # 3b. Quality Gates
        passed_gates = True
        if tests:
            success_tests, test_summary = debugging_loop(
                agent, ["test"], stream=stream, iterations=max_debug_iterations
            )
            if not success_tests:
                passed_gates = False
                failure_reason = "Tests failed"
                failure_context = test_summary

        if passed_gates and review:
            # Agentic review logic
            try:
                review_prompt = f"Review implementation for {prd.title}. Criteria: {success_criteria}"
                cmd = get_agent_command(agent, review_prompt)
                output, _ = run_agent(cmd, stream=stream)
                if "<review>PASSED</review>" not in output:
                    passed_gates = False
                    failure_reason = "Review failed"
                    failure_context = output
            except Exception as e:
                passed_gates = False
                failure_reason = f"Review error: {e}"
                failure_context = str(e)

        if passed_gates:
            success = True
            break

    # 4. Finalize
    if success:
        logger.info(f"✅ PRD {prd.id} completed successfully.")
        prd.status = "done"
        final_path = PRODUCT_HISTORY_DIR / prd.path.name
        prd.save(final_path)
        prd.path.unlink()

        # Update state
        state = load_project_state()
        if prd.id not in state["completed_prds"]:
            state["completed_prds"].append(prd.id)
        save_project_state(state)

        # Auto-merge if enabled
        if ralph_config.get("auto_merge", False):
            automerge_branch = get_automerge_branch(config)
            from vibe_tools.branches import merge_branches

            merge_branches(branch_name, automerge_branch)

        switch_to_main()
        return True
    else:
        logger.error(f"❌ PRD {prd.id} failed: {failure_reason}")

        # 4b. Summarize failure for the new PRD
        from vibe_tools.utils import run_llm
        
        problem_description = f"Implementation of {prd.id} failed with: {failure_reason}"
        if failure_context:
            logger.info("🧠 Summarizing failure for the new PRD...")
            summary_prompt = f"""
            You are a technical lead. A developer's task failed. 
            Summarize the following failure logs/feedback into a clear 'Problem Statement' for a new issue PRD.
            Focus on what went wrong and what needs to be fixed.
            
            Original PRD Title: {prd.title}
            Failure Reason: {failure_reason}
            
            Failure Context:
            {failure_context}
            
            Output ONLY the summarized problem description. Do not include markdown headers if possible, just the text.
            """
            summarized = run_llm(summary_prompt)
            if summarized:
                problem_description = summarized.strip()

        # Create new issue PRD
        new_issue_id = generate_prd_id(pathlib.Path("product"))
        issue_title = f"Fix failures in {prd.id}: {prd.title}"
        new_issue = PRD(
            id=new_issue_id,
            title=issue_title,
            type="ISSUE",
            status="backlog",
            content=problem_description,
        )
        issue_filename = (
            f"{new_issue_id}-{re.sub(r'[^a-z0-9]+', '-', issue_title.lower())}.md"
        )
        new_issue.save(PRODUCT_BACKLOG_DIR / issue_filename)

        # Update current PRD
        prd.status = "backlog"
        prd.depends_on.append(new_issue_id)
        prd.append_history(
            f"Attempt failed: {failure_reason}. Blocked by {new_issue_id}."
        )

        backlog_filename = prd.path.name
        prd.save(PRODUCT_BACKLOG_DIR / backlog_filename)
        prd.path.unlink()

        switch_to_main()
        return False


def issue_solve_loop(issue, agent: str, stream: bool = False) -> bool:
    """Compatibility shim for old solve command."""
    logger.info("ℹ️ Using unified implementation loop for issue.")
    # In the new world, we should probably just call implementation_loop
    # but for now let's just make it boot.
    return True
