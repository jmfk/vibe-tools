"""
Core engine for the modular project lifecycle.
Includes the Planner Agent, Reconciliation Loops, and Implementation Loop.
"""

import hashlib
import json
import pathlib
import yaml
from typing import Any, List, Dict

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
    get_prompt,
    load_project_state,
    save_project_state,
    check_plan_dependencies,
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
            logger.info(f"✅ {self.name} reconciliation successful.")
            return True
        else:
            logger.error(f"❌ {self.name} reconciliation failed or incomplete.")
            return False


def run_planner_agent(agent: str, stream: bool = False) -> bool:
    """Runs the Planner Agent to generate Markdown plans and project-plan.yaml index."""
    # Reset plans in project-state.json
    state = load_project_state()
    state["plans"] = {}
    save_project_state(state)

    architecture = ARCHITECTURE.read_text() if ARCHITECTURE.exists() else "NOT FOUND"
    prds = ""
    for prd_file in collect_prd_files():
        # Try to find corresponding markdown spec in specs/
        # prd_01_name.yaml -> PRD-01-name.md
        parts = prd_file.stem.split("_")
        spec_path = "NOT FOUND"
        if len(parts) >= 2:
            prd_id = parts[1]
            spec_matches = list(pathlib.Path("specs").glob(f"PRD-{prd_id}-*.md"))
            if spec_matches:
                spec_path = str(spec_matches[0])

        prds += f"\n--- {prd_file.name} ---\nYAML Path: {prd_file}\nMarkdown Spec Path: {spec_path}\nContent:\n{prd_file.read_text()}\n"

    try:
        prompt_base = get_prompt("planner_prompt.txt")
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        return False

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


def _extract_all_plans(index_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Helper to extract all plan objects from the nested phases/prds structure."""
    all_plans = []
    phases = index_data.get("phases", {})

    # Standard phases: setup, infra, cicd
    for phase_name in ["setup", "infra", "cicd"]:
        phase_data = phases.get(phase_name, {})
        all_plans.extend(phase_data.get("plans", []))

    # Implementation phase: grouped by PRDs
    implementation = phases.get("implementation", {})
    prds = implementation.get("prds", [])
    for prd in prds:
        all_plans.extend(prd.get("plans", []))

    return all_plans


def normalize_plans(agent: str, stream: bool = False) -> bool:
    """Normalizes Markdown plans in plans/ into machine-consumable YAML files."""
    from vibe_tools.utils import migrate_to_project_dir

    migrate_to_project_dir()

    if not PROJECT_PLAN.exists():
        logger.error(f"❌ {PROJECT_PLAN} not found. Planning failed.")
        return False

    try:
        index_data = yaml.safe_load(PROJECT_PLAN.read_text())
    except Exception as e:
        logger.error(f"Failed to parse {PROJECT_PLAN}: {e}")
        return False

    all_plans = _extract_all_plans(index_data)
    if not all_plans:
        logger.warning("No plans found in project-plan.yaml index.")
        return True

    try:
        prompt_base = get_prompt("plan_normalization_prompt.txt")
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        return False

    for plan_info in all_plans:
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

            # Sync to project-state.json
            try:
                plan_data = yaml.safe_load(clean_output)
                state = load_project_state()
                plan_id = plan_data.get("id")
                if plan_id:
                    state["plans"][plan_id] = {
                        "status": plan_data.get("status", "pending"),
                        "depends_on": plan_data.get("dependencies", []),
                        "title": plan_data.get("title", plan_id),
                    }
                    save_project_state(state)
            except Exception as e:
                logger.error(f"Failed to sync plan {plan_file.name} to state: {e}")
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

    phases = index_data.get("phases", {})
    if not phases:
        logger.warning("No phases found in project-plan.yaml index.")
        return True

    from vibe_tools.cli import load_config

    config = load_config()
    ralph_config = config.get("ralph", {})
    review = ralph_config.get("review", True)
    tests = ralph_config.get("tests", True)

    # Order of phases to execute
    phase_order = ["setup", "infra", "implementation", "cicd"]

    for phase_name in phase_order:
        if phase_name not in phases:
            continue

        phase_data = phases[phase_name]
        plans_to_run = []

        if phase_name == "implementation":
            # For implementation, we have nested PRDs
            prds = phase_data.get("prds", [])
            for prd in prds:
                plans_to_run.extend(prd.get("plans", []))
        else:
            # For other phases, plans are top-level
            plans_to_run = phase_data.get("plans", [])

        if not plans_to_run:
            continue

        logger.info(f"📍 Starting Phase: {phase_name.upper()}")

        for plan_info in plans_to_run:
            plan_id = plan_info.get("id")

            # Check plan-level dependencies from project-state.json
            state = load_project_state()
            if plan_id in state.get("plans", {}):
                if state["plans"][plan_id].get("status") == "completed":
                    continue

                missing_deps = check_plan_dependencies(plan_id, state)
                if missing_deps:
                    logger.warning(
                        f"⚠️ Skipping plan {plan_id}: Missing dependencies: {', '.join(missing_deps)}"
                    )
                    continue

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

            logger.info(f"🚀 Executing Plan: {plan_data.get('title')} ({plan_id})")
            branch_name = f"feature/{plan_id}"
            _switch_to_branch(branch_name, agent, plan_id, stream=stream)

            success = False
            for i in range(1, MAX_ITERATIONS + 1):
                logger.info(f"🛠️ [IMPLEMENTATION] Iteration {i}/{MAX_ITERATIONS}")

                # 1. Implementation
                try:
                    prompt_template = get_prompt("implementation_prompt.txt")
                except FileNotFoundError as e:
                    logger.error(f"Error: {e}")
                    return False

                prompt = prompt_template.format(
                    title=plan_data.get("title"),
                    description=plan_data.get("description"),
                    success_criteria=chr(10).join(
                        ["- " + c for c in plan_data.get("success_criteria", [])]
                    ),
                )
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
                    try:
                        review_prompt_template = get_prompt(
                            "implementation_review_prompt.txt"
                        )
                    except FileNotFoundError as e:
                        logger.error(f"Error: {e}")
                        return False

                    review_prompt = review_prompt_template.format(
                        title=plan_data.get("title"),
                        description=plan_data.get("description"),
                        success_criteria=chr(10).join(
                            ["- " + c for c in plan_data.get("success_criteria", [])]
                        ),
                    )
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

                # Update status in project-state.json
                state = load_project_state()
                if plan_id not in state["plans"]:
                    state["plans"][plan_id] = {}
                state["plans"][plan_id]["status"] = "completed"
                save_project_state(state)

                # Update status in individual YAML (for backward compatibility/redundancy)
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
