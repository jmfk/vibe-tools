import json
import pathlib
import sys

from vibe_tools.cost import AGENT_DEFAULT_MODEL, CostLogger
from vibe_tools.testing import ProjectTester
from vibe_tools.utils import (
    get_agent_command,
    logger,
    run_agent,
    get_prompt,
    log_issue,
    log_start,
    log_success,
)

STATE_FILE = pathlib.Path(".test_fix_state.json")
MAX_ITERATIONS = 10
COMPLETION_PROMISE = "<promise>DONE</promise>"


def save_state(iteration, last_error):
    """Saves the current state to a file."""
    state = {
        "iteration": iteration,
        "last_error": last_error,
    }
    STATE_FILE.write_text(json.dumps(state, indent=2))


def load_state():
    """Loads state from the state file if it exists."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception as e:
            print(f"Warning: Failed to load state file: {e}")
            return None
    return None


def clear_state():
    """Deletes the state file."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()


def run_tests(caffeinate=False, fast=False):
    """Runs backend and frontend tests."""
    tester = ProjectTester()
    return tester.run_tests(caffeinate=caffeinate, changed_only=fast)


def run_test_fix_loop(agent="cursor-agent", caffeinate=False, fast=False, stream=False):
    from vibe_tools.cli import load_config

    logger.info("--- Starting Test and Fix Loop ---")

    config = load_config()
    iterations_config = config.get("iterations", {})
    max_iterations = iterations_config.get("test_fix", MAX_ITERATIONS)
    cost_logger = CostLogger(config)

    log_start("test_fix", "Starting full test and fix cycle")

    saved_state = load_state()
    start_iteration = saved_state["iteration"] if saved_state else 1

    if saved_state:
        logger.info(f"[RESTART] Resuming Test and Fix loop at iteration {start_iteration}")

    for i in range(start_iteration, max_iterations + 1):
        logger.info(f"\n[TEST_FIX LOOP] [PHASE: test] (Iteration {i}/{max_iterations})")

        test_output, tests_passed, env_failures, failed_targets = run_tests(caffeinate=caffeinate, fast=fast)

        if env_failures:
            log_issue("test_fix", i, max_iterations, f"Environment failure: {', '.join(env_failures)}")
            logger.error(
                f"❌ ENVIRONMENT FAILURE DETECTED: Commands missing for targets: {', '.join(env_failures)}"
            )
            logger.error("Please ensure your environment is set up correctly (npm install, etc.).")
            sys.exit(127)

        if tests_passed:
            log_success("test_fix", "All tests and linting passed.")
            logger.info("✅ All tests and linting passed!")
            clear_state()
            break

        tester = ProjectTester()
        summary = tester.get_summary(failed_targets)
        log_issue("test_fix", i, max_iterations, summary)
        logger.info(f"❌ Tests or linting failed. [PHASE: fix] Asking {agent} to fix...")

        try:
            prompt_base = get_prompt("test_fix_prompt.txt")
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)

        prompt = prompt_base.replace("{test_output}", test_output)

        cmd = get_agent_command(agent, prompt)
        agent_output, _ = run_agent(cmd, caffeinate=caffeinate, stream=stream)

        cost_logger.log_run(
            agent=agent,
            model=AGENT_DEFAULT_MODEL.get(agent, "unknown"),
            prompt=prompt,
            output=agent_output,
            prd_name="N/A",
            iteration=i,
            phase="test_fix",
            purpose="fixing_test_failures",
        )

        save_state(i + 1, test_output)

        if i == max_iterations:
            logger.error(f"FAILED: Could not fix all errors within {max_iterations} iterations.")
            sys.exit(1)

    logger.info("--- Test and Fix Loop Finished ---")
