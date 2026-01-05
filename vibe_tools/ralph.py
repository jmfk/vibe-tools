"""
Core engine for the modular project lifecycle.
Includes the Planner Agent, Reconciliation Loops, and Implementation Loop.
"""

import hashlib
import json
import pathlib
import yaml
from typing import Any, List

from vibe_tools.cost import AGENT_DEFAULT_MODEL, CostLogger
from vibe_tools.utils import (
    PRD_DIR,
    PROJECT_PLAN,
    ARCHITECTURE,
    get_agent_command,
    run_agent,
    run_command,
    get_file_hash,
    logger,
    get_main_branch,
    is_dirty,
    collect_prd_files,
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
    ):
        self.name = name
        self.desired_file = desired_file
        self.current_file = current_file
        self.agent = agent
        self.stream = stream
        self.caffeinate = caffeinate
        self.instructions = []

    def run(self) -> bool:
        """Executes the reconciliation loop."""
        logger.info(f"🔄 Starting {self.name} Loop...")

        if not self.desired_file.exists():
            logger.error(f"❌ Desired file {self.desired_file} not found.")
            return False

        # 1. Compare Desired vs Current
        current_content = (
            self.current_file.read_text() if self.current_file.exists() else "NOT FOUND"
        )

        # 2. Prepare prompt
        custom_instructions = ""
        if self.instructions:
            custom_instructions = "\nADDITIONAL PHASE-SPECIFIC INSTRUCTIONS:\n"
            for idx, inst in enumerate(self.instructions, 1):
                custom_instructions += f"{idx}. {inst}\n"

        prompt = f"""You are in the '{self.name}' phase of the project lifecycle.
Your goal is to reconcile the DESIRED state (defined in {self.desired_file.name}) with the ACTUAL state (described in {self.current_file.name} and the current codebase).

DESIRED STATE ({self.desired_file.name}):
{self.desired_file.read_text()}

ACTUAL STATE ({self.current_file.name}):
{current_content}

INSTRUCTIONS:
1. Examine the current codebase and the actual state.
2. If an ACTUAL state exists, perform a MIGRATION or UPGRADE to reach the DESIRED state.
3. If no ACTUAL state exists, perform a fresh initialization.
4. Perform any necessary actions (coding, configuration, setup, migrations) to match the desired state.
5. Update {self.current_file.name} to accurately reflect the new actual state once complete.{custom_instructions}
6. Include {COMPLETION_PROMISE} in your response when the reconciliation is successful.
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
    """Runs the Planner Agent to generate Markdown plans and project-plan.yaml index."""
    architecture = ARCHITECTURE.read_text() if ARCHITECTURE.exists() else "NOT FOUND"
    prds = ""
    for prd_file in collect_prd_files():
        prds += f"\n--- {prd_file.name} ---\n{prd_file.read_text()}\n"

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

    if code == 0 and COMPLETION_PROMISE in output:
        # Step 2: Normalize the generated plans
        return normalize_plans(agent, stream=stream)
    return False


def normalize_plans(agent: str, stream: bool = False) -> bool:
    """Normalizes Markdown plans in plans/ into machine-consumable YAML files."""
    if not PROJECT_PLAN.exists():
        logger.error(f"❌ {PROJECT_PLAN} not found. Planning failed.")
        return False

    try:
        index_data = yaml.safe_load(PROJECT_PLAN.read_text())
    except Exception as e:
        logger.error(f"Failed to parse {PROJECT_PLAN}: {e}")
        return False

    plans = index_data.get("plans", [])
    if not plans:
        logger.warning("No plans found in project-plan.yaml index.")
        return True

    from vibe_tools.templates import TEMPLATES

    prompt_base = TEMPLATES.get("plan_normalization_prompt.txt", "")

    for plan_info in plans:
        plan_file = pathlib.Path(plan_info.get("file"))
        if not plan_file.exists():
            logger.error(f"Plan file {plan_file} not found.")
            continue

        yaml_path = plan_file.with_suffix(".yaml")
        # Optimization: skip if yaml is newer than markdown
        if yaml_path.exists() and yaml_path.stat().st_mtime > plan_file.stat().st_mtime:
            continue

        logger.info(f"🔄 Normalizing plan: {plan_file.name} -> {yaml_path.name}...")
        prompt = prompt_base.replace("{plan_content}", plan_file.read_text())
        cmd = get_agent_command(agent, prompt)
        output, code = run_agent(cmd, stream=stream)

        if code == 0:
            # Clean markdown code fences if present
            clean_output = output.strip()
            if clean_output.startswith("```"):
                lines = clean_output.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_output = "\n".join(lines).strip()

            yaml_path.write_text(clean_output)
            logger.info(f"✅ Saved: {yaml_path}")
        else:
            logger.error(f"❌ Failed to normalize plan {plan_file.name}")
            return False

    return True


def implementation_loop(agent: str, stream: bool = False) -> bool:
    """Executes the implementation phase based on granular YAML plans."""
    if not PROJECT_PLAN.exists():
        logger.error(f"❌ {PROJECT_PLAN} not found.")
        return False

    try:
        index_data = yaml.safe_load(PROJECT_PLAN.read_text())
    except Exception as e:
        logger.error(f"Failed to parse {PROJECT_PLAN}: {e}")
        return False

    plans_list = index_data.get("plans", [])
    if not plans_list:
        logger.warning("No plans found in project-plan.yaml index.")
        return True

    from vibe_tools.cli import load_config

    config = load_config()
    ralph_config = config.get("ralph", {})
    review = ralph_config.get("review", True)
    tests = ralph_config.get("tests", True)

    for plan_info in plans_list:
        plan_id = plan_info.get("id")
        plan_md_path = pathlib.Path(plan_info.get("file"))
        plan_yaml_path = plan_md_path.with_suffix(".yaml")

        if not plan_yaml_path.exists():
            logger.error(f"Normalized plan {plan_yaml_path} not found. Skipping.")
            continue

        try:
            plan_data = yaml.safe_load(plan_yaml_path.read_text())
        except Exception as e:
            logger.error(f"Failed to parse {plan_yaml_path}: {e}")
            continue

        if plan_data.get("status") == "completed":
            continue

        logger.info(f"🚀 Executing Plan: {plan_data.get('title')} ({plan_id})")
        branch_name = f"feature/{plan_id}"
        _switch_to_branch(branch_name, agent, plan_id, stream=stream)

        success = False
        for i in range(1, MAX_ITERATIONS + 1):
            logger.info(f"🛠️ [IMPLEMENTATION] Iteration {i}/{MAX_ITERATIONS}")

            # 1. Implementation
            prompt = f"""You are the Implementation Agent. Your task is to execute a specific plan.

PLAN TO EXECUTE:
Title: {plan_data.get('title')}
Description: {plan_data.get('description')}
Success Criteria:
{chr(10).join(['- ' + c for c in plan_data.get('success_criteria', [])])}

TASK:
1. Implement the code and configuration required for THIS PLAN.
2. Verify your changes against the success criteria.
3. Include {COMPLETION_PROMISE} in your response when the implementation is finished.
"""
            cmd = get_agent_command(agent, prompt)
            output, code = run_agent(cmd, stream=stream)

            if code != 0 or COMPLETION_PROMISE not in output:
                logger.warning(f"⏳ Implementation in progress for {plan_id}...")
                continue

            # 2. Quality Gates
            logger.info("🧪 Running Quality Gates...")
            passed_gates = True

            if tests:
                test_targets = plan_data.get("test_targets", ["test"])
                for target in test_targets:
                    logger.info(f"Running test target: {target}")
                    _, test_code = run_command(["make", target], check=False)
                    if test_code != 0:
                        logger.error(f"❌ Test target {target} failed.")
                        passed_gates = False
                        break

            if passed_gates and review:
                logger.info("🔎 Running Agentic Review...")
                review_prompt = f"""Review the changes for the following plan:
TITLE: {plan_data.get('title')}
DESCRIPTION: {plan_data.get('description')}
SUCCESS CRITERIA:
{chr(10).join(['- ' + c for c in plan_data.get('success_criteria', [])])}

If the implementation meets all requirements, respond with: <review>PASSED</review>
Otherwise, list the issues.
"""
                review_cmd = get_agent_command(agent, review_prompt)
                review_output, _ = run_agent(review_cmd, stream=stream)
                if "<review>PASSED</review>" not in review_output:
                    logger.error("❌ Agentic review failed.")
                    passed_gates = False

            if passed_gates:
                success = True
                break
            else:
                logger.info("🔄 Retrying implementation to fix quality issues...")

        if success:
            logger.info(f"✅ Plan {plan_id} completed successfully.")
            # Commit changes
            commit_prompt = f"Commit changes for plan: {plan_data.get('title')}. Ensure all success criteria were met."
            commit_cmd = get_agent_command(agent, commit_prompt)
            run_agent(commit_cmd, stream=stream)

            # Update status
            plan_data["status"] = "completed"
            plan_yaml_path.write_text(yaml.dump(plan_data))

            # Switch back to main
            _switch_to_main()
        else:
            logger.error(
                f"❌ Failed to complete plan {plan_id} after {MAX_ITERATIONS} iterations."
            )
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
                    f"vibe: automatic commit of partial work on {current_branch}",
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
            import sys

            sys.exit(1)
