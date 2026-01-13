import json
import pathlib
import sys

from vibe_tools.cost import AGENT_DEFAULT_MODEL, CostLogger
from vibe_tools.testing import ProjectTester
from vibe_tools.utils import (
    get_agent_command,
    get_prompt,
    log_issue,
    log_start,
    log_success,
    logger,
    run_agent,
    out_warn,
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
            out_warn(f"Warning: Failed to load state file: {e}")
            return None
    return None


def clear_state():
    """Deletes the state file."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()


def run_tests(fast=False):
    """Runs backend and frontend tests."""
    tester = ProjectTester()
    return tester.run_tests(changed_only=fast)


def run_test_fix_loop(agent="cursor-agent", fast=False, stream=False):
    from vibe_tools.cli import load_config

    logger.info("--- Starting Optimized Test and Fix Loop ---")

    config = load_config()
    iterations_config = config.get("iterations", {})
    max_iterations = iterations_config.get("test_fix", MAX_ITERATIONS)
    cost_logger = CostLogger(config)

    log_start("test_fix", "Starting optimized test and fix cycle")

    saved_state = load_state()
    start_iteration = saved_state["iteration"] if saved_state else 1

    if saved_state:
        logger.info(f"[RESTART] Resuming Test and Fix loop at iteration {start_iteration}")

    tester = ProjectTester()

    for i in range(start_iteration, max_iterations + 1):
        logger.info(f"\n[TEST_FIX LOOP] [PHASE: test-all] (Iteration {i}/{max_iterations})")

        test_output, tests_passed, env_failures, failed_targets = run_tests(fast=fast)

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

        # Identify specific failing tests
        failures = tester.parse_failures(test_output)
        num_failures = len(failures)

        if num_failures > 0:
            logger.info(f"❌ {num_failures} individual test failures detected. Fixing them one by one...")

            for idx, failure in enumerate(failures, 1):
                test_id = failure["id"]
                logger.info(f"\n[FIX {idx}/{num_failures}] Working on: {test_id}")

                # Ask agent to fix this specific test
                try:
                    prompt_base = get_prompt("test_fix_prompt.txt")
                except FileNotFoundError:
                    logger.error("Prompt template 'test_fix_prompt.txt' not found.")
                    sys.exit(1)

                # Get the relevant output for just this test if possible, or use full output
                # For now, we'll provide the specific test we want fixed
                specific_prompt = f"SPECIFIC TARGET: Fix failing test '{test_id}'\n\n{prompt_base}"
                prompt = specific_prompt.replace("{test_output}", test_output)

                cmd = get_agent_command(agent, prompt)
                agent_output, _ = run_agent(cmd, stream=stream)

                cost_logger.log_run(
                    agent=agent,
                    model=AGENT_DEFAULT_MODEL.get(agent, "unknown"),
                    prompt=prompt,
                    output=agent_output,
                    prd_name="N/A",
                    iteration=i,
                    phase="test_fix",
                    purpose=f"fixing_test_{test_id}",
                )

                # Verify this specific test
                verify_output, fixed = tester.run_single_test(failure)
                if fixed:
                    logger.info(f"✅ Test fixed: {test_id}")
                else:
                    logger.warning(f"⚠️ Test STILL failing: {test_id}")
                    # We continue to the next one anyway, or we could retry?
                    # The plan says "repeat until the whole list of failing tests are fixed"
                    # which implies we might loop again in the next iteration.
        else:
            # No specific test failures parsed (maybe linting or generic error)
            summary = tester.get_summary(failed_targets)
            log_issue("test_fix", i, max_iterations, summary)
            logger.info(f"❌ Targets failed but no specific tests parsed. [PHASE: fix] Asking {agent} to fix all...")

            try:
                prompt_base = get_prompt("test_fix_prompt.txt")
            except FileNotFoundError:
                sys.exit(1)

            prompt = prompt_base.replace("{test_output}", test_output)
            cmd = get_agent_command(agent, prompt)
            agent_output, _ = run_agent(cmd, stream=stream)

            cost_logger.log_run(
                agent=agent,
                model=AGENT_DEFAULT_MODEL.get(agent, "unknown"),
                prompt=prompt,
                output=agent_output,
                prd_name="N/A",
                iteration=i,
                phase="test_fix",
                purpose="fixing_generic_failures",
            )

        save_state(i + 1, test_output)

        if i == max_iterations:
            logger.error(f"FAILED: Could not fix all errors within {max_iterations} iterations.")
            sys.exit(1)

    logger.info("--- Test and Fix Loop Finished ---")
