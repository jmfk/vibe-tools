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
    PLANS_DIR,
    COMPILED_PLANS_DIR,
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
    log_issue,
    log_start,
    log_success,
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
        log_start(
            self.name,
            f"Reconciling {self.desired_file.name} vs {self.current_file.name}",
        )
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
            log_success(self.name, "Reconciliation successful.")
            logger.info(f"✅ {self.name} reconciliation successful.")
            return True
        else:
            log_issue(self.name, 1, 1, "Reconciliation failed or incomplete")
            logger.error(f"❌ {self.name} reconciliation failed or incomplete.")
            return False


def run_planner_agent(agent: str, stream: bool = False) -> bool:
    """Runs the Planner Agent to generate Markdown plans and project-plan.yaml index."""
    log_start("planner", "Generating implementation plans")
    # Reset plans in project-state.json
    state = load_project_state()
    state["plans"] = {}
    save_project_state(state)

    architecture = ARCHITECTURE.read_text() if ARCHITECTURE.exists() else "NOT FOUND"

    # Read specs from specs/ as the primary source of truth
    specs_content = ""
    from vibe_tools.utils import SPECS_DIR

    if SPECS_DIR.exists():
        for spec_file in sorted(SPECS_DIR.rglob("*.md")):
            specs_content += f"\n\n--- FILE: {spec_file} ---\n{spec_file.read_text()}\n--- END FILE: {spec_file} ---"
    else:
        specs_content = "No specs/ directory found."

    try:
        prompt_base = get_prompt("planner_prompt.txt")
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        return False

    prompt = f"""{prompt_base}

ARCHITECTURE:
{architecture}

SPECS (Primary Requirements):
{specs_content}

INSTRUCTIONS:
1. Review the architecture and the provided specs.
2. Create detailed implementation plans for each feature/change.
3. Write each plan as a separate Markdown file in 'project/plans/'.
4. Each plan must follow the structure:
   - # Plan: [Title]
   - ID: [unique_slug]
   - Status: pending
   - Description: ...
   - Success Criteria:
     - [ ] ...
   - Dependencies: [list of plan IDs]
5. Finally, update 'project/project-plan.yaml' to index all plans.
"""
    cmd = get_agent_command(agent, prompt)
    output, code = run_agent(cmd, stream=stream)

    if code == 0 and COMPLETION_PROMISE in output:
        # Step 2: Normalize the generated plans
        from vibe_tools.normalize import normalize_plans

        success = normalize_plans(agent, stream=stream)
        if success:
            log_success("planner", "Plans generated and normalized successfully.")
        else:
            log_issue("planner", 1, 1, "Normalization of plans failed.")
        return success

    log_issue("planner", 1, 1, "Planner agent failed to complete.")
    return False


def generate_prd_plan() -> bool:
    """Generates a project-plan.yaml that tracks PRDs directly instead of granular plans."""
    prds = collect_prd_files()
    if not prds:
        logger.warning("No PRDs found in project/prds/ to generate plan.")
        return False

    plan_data = {
        "phases": {
            "setup": {"plans": []},
            "infra": {"plans": []},
            "implement": {"prds": []},
            "cicd": {"plans": []},
        }
    }

    state = load_project_state()

    for prd_path in prds:
        prd_id = prd_path.stem
        # Structure it so implementation_loop can find it as a single 'plan' per PRD
        plan_data["phases"]["implement"]["prds"].append(
            {
                "id": prd_id,
                "plans": [
                    {
                        "id": prd_id,
                        "file": str(prd_path),
                        "status": state.get("plans", {})
                        .get(prd_id, {})
                        .get("status", "pending"),
                        "is_direct_prd": True,
                    }
                ],
            }
        )

        # Also ensure it's in state["plans"]
        if prd_id not in state["plans"]:
            state["plans"][prd_id] = {
                "status": "pending",
                "depends_on": [],
                "title": prd_id.replace("prd_", "").replace("_", " ").title(),
            }

    save_project_state(state)

    with open(PROJECT_PLAN, "w") as f:
        yaml.dump(plan_data, f, sort_keys=False)

    logger.info(f"✅ Generated PRD-based project plan: {PROJECT_PLAN}")
    return True


def debugging_loop(
    agent: str, targets: List[str], stream: bool = False, iterations: int = 5
) -> bool:
    """Runs a set of test targets in a loop until they pass or max iterations reached."""
    from vibe_tools.testing import ProjectTester
    from vibe_tools.cost import CostLogger
    from vibe_tools.cli import load_config

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
        from vibe_tools.cost import AGENT_DEFAULT_MODEL

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


def implementation_loop(agent: str, stream: bool = False) -> bool:
    """Executes the implementation phase based on granular YAML plans or direct PRDs."""
    plans_from_prds = False
    if not PROJECT_PLAN.exists():
        logger.info(
            f"ℹ️ {PROJECT_PLAN} not found. Falling back to direct PRD implementation."
        )
        prds = collect_prd_files()
        if not prds:
            logger.error(f"❌ No PRDs found in {PRD_DIR}.")
            return False

        plans_to_run_direct = []
        for prd_path in prds:
            plan_id = prd_path.stem
            plans_to_run_direct.append(
                {"id": plan_id, "file": str(prd_path), "is_direct_prd": True}
            )

        phases = {
            "implement": {"prds": [{"id": "direct", "plans": plans_to_run_direct}]}
        }
        plans_from_prds = True
    else:
        try:
            index_data = yaml.safe_load(PROJECT_PLAN.read_text())
        except Exception as e:
            logger.error(f"Failed to parse {PROJECT_PLAN}: {e}")
            return False
        phases = index_data.get("phases", {})

    if not phases:
        logger.warning("No phases found in project-plan.yaml index.")
        return True

    config = load_config()
    iterations_config = config.get("iterations", {})
    max_impl_iterations = iterations_config.get("implementation", MAX_ITERATIONS)
    max_debug_iterations = iterations_config.get("debug", 5)

    ralph_config = config.get("ralph", {})
    review = ralph_config.get("review", True)
    tests = ralph_config.get("tests", True)

    # Order of phases to execute
    phase_order = ["setup", "implement", "testing", "infra", "cicd"]

    for phase_name in phase_order:
        if phase_name not in phases:
            continue

        phase_data = phases[phase_name]
        plans_to_run = []

        if phase_name == "implement":
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
            is_direct_prd = plan_info.get("is_direct_prd", False)

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

            plan_file_path = pathlib.Path(plan_info.get("file"))

            if is_direct_prd:
                # For direct PRD, the file is the YAML already
                plan_yaml_path = plan_file_path
            else:
                # For planned implementation, the file is the Markdown plan
                plan_yaml_path = COMPILED_PLANS_DIR / (plan_file_path.stem + ".yaml")

            if not plan_yaml_path.exists():
                logger.error(f"Normalized plan {plan_yaml_path} not found. Skipping.")
                continue

            try:
                plan_data = yaml.safe_load(plan_yaml_path.read_text())
            except Exception as e:
                logger.error(f"Failed to parse {plan_yaml_path}: {e}")
                continue

            if is_direct_prd:
                # Synthesize plan_data from PRD structure if needed
                # Normalized PRDs have SYSTEM_CONTRACT, DOMAIN_MODEL, CAPABILITIES, OUTPUT_TARGETS
                # We can use the whole YAML as the description
                title = plan_id.replace("prd_", "").replace("_", " ").title()
                description = plan_yaml_path.read_text()

                # Extract success criteria from various parts of the PRD
                capabilities = plan_data.get("CAPABILITIES", {})
                success_criteria = []
                if isinstance(capabilities.get("interaction_mechanisms"), list):
                    success_criteria.extend(capabilities["interaction_mechanisms"])
                if isinstance(capabilities.get("patterns"), list):
                    success_criteria.extend(capabilities["patterns"])
                if isinstance(capabilities.get("routing"), list):
                    success_criteria.extend(capabilities["routing"])

                if not success_criteria:
                    success_criteria = [
                        "Implement all capabilities defined in the PRD."
                    ]

                test_targets = ["test"]
            else:
                title = plan_data.get("title", plan_id)
                description = plan_data.get("description", "")
                success_criteria = plan_data.get("success_criteria", [])
                test_targets = plan_data.get("test_targets", ["test"])

            logger.info(f"🚀 Executing Plan: {title} ({plan_id})")
            log_start("implement", f"Plan: {title} ({plan_id})")
            branch_name = f"feature/{plan_id}"
            _switch_to_branch(branch_name, agent, plan_id, stream=stream)

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

                # 2. Quality Gates
                logger.info("🧪 Running Quality Gates...")
                passed_gates = True

                if tests:
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
                # Commit changes
                commit_prompt = f"Commit changes for plan: {title}. Ensure all success criteria were met."
                commit_cmd = get_agent_command(agent, commit_prompt)
                run_agent(commit_cmd, stream=stream)

                # Update status in project-state.json
                state = load_project_state()
                if plan_id not in state["plans"]:
                    state["plans"][plan_id] = {}
                state["plans"][plan_id]["status"] = "completed"

                # If it's a direct PRD, also mark it in completed_prds
                if is_direct_prd:
                    if plan_id not in state.get("completed_prds", []):
                        state["completed_prds"].append(plan_id)

                save_project_state(state)

                # Update status in individual YAML (for backward compatibility/redundancy)
                # Only if it's not a direct PRD (we don't want to modify the source PRD YAML if possible,
                # but project-plan.yaml does it for plans. For PRDs we use state.json mostly)
                if not is_direct_prd:
                    plan_data["status"] = "completed"
                    plan_yaml_path.write_text(yaml.dump(plan_data))

                # Switch back to main
                _switch_to_main()
            else:
                logger.error(
                    f"❌ Failed to complete plan {plan_id} after {max_impl_iterations} iterations."
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
