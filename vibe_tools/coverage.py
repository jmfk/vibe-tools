import pathlib
import sys

from vibe_tools.cost import AGENT_DEFAULT_MODEL, CostLogger
from vibe_tools.testing import ProjectTester
from vibe_tools.utils import get_agent_command, logger, run_agent, run_command

PROMPTS_DIR = pathlib.Path("prompts")
COVERAGE_PROMPT_TEMPLATE = PROMPTS_DIR / "coverage_improvement_prompt.txt"
MAX_ITERATIONS = 5
COMPLETION_PROMISE = "<promise>DONE</promise>"


def get_coverage_report(caffeinate=False):
    """Runs coverage and returns the full report and total coverage percentage."""
    tester = ProjectTester()
    return tester.get_coverage_report(caffeinate=caffeinate)


def improve_coverage_loop(agent="cursor-agent", caffeinate=False):
    from vibe_tools.cli import load_config

    logger.info("--- Starting Coverage Improvement Loop ---")

    config = load_config()
    cost_logger = CostLogger(config)

    if not PROMPTS_DIR.exists():
        logger.error("Error: prompts directory not found. Please run 'vibe init' first.")
        sys.exit(1)

    for i in range(1, MAX_ITERATIONS + 1):
        report, current_cov = get_coverage_report(caffeinate=caffeinate)
        logger.info(
            f"\n[COVERAGE LOOP] [PHASE: report] (Iteration {i}) Current Total Coverage: {current_cov}%"
        )

        if current_cov >= 100:
            logger.info("100% coverage achieved!")
            break

        target_cov = current_cov + (0.3 * (100 - current_cov))
        logger.info(f"Targeting improvement to at least {target_cov:.1f}%")

        if not COVERAGE_PROMPT_TEMPLATE.exists():
            logger.error(
                f"Error: Coverage prompt template not found at {COVERAGE_PROMPT_TEMPLATE}. Please run 'vibe init'."
            )
            sys.exit(1)

        prompt_base = COVERAGE_PROMPT_TEMPLATE.read_text()
        prompt = (
            prompt_base.replace("{report}", report)
            .replace("{current_cov}", str(current_cov))
            .replace("{target_cov}", f"{target_cov:.1f}")
        )

        logger.info(
            f"[COVERAGE LOOP] [PHASE: improve] (Iteration {i}) Calling agent to improve coverage..."
        )
        cmd = get_agent_command(agent, prompt)
        output, _ = run_agent(cmd, caffeinate=caffeinate)

        cost_logger.log_run(
            agent=agent,
            model=AGENT_DEFAULT_MODEL.get(agent, "unknown"),
            prompt=prompt,
            output=output,
            prd_name="N/A",
            iteration=i,
            phase="coverage",
            purpose="improving_coverage",
        )

        # Verify if tests still pass
        logger.info(f"[COVERAGE LOOP] [PHASE: verify] (Iteration {i}) Verifying tests...")
        _, test_exit_code = run_command(["make", "test"], check=False, caffeinate=caffeinate)
        if test_exit_code != 0:
            logger.warning(
                "⚠️ Warning: Tests are failing after agent changes! Asking agent to fix..."
            )
            fix_prompt = f"The tests are failing after your last changes. Please fix them.\n\nERROR:\n{output}"
            cmd_fix = get_agent_command(agent, fix_prompt)
            fix_output, _ = run_agent(cmd_fix, caffeinate=caffeinate)
            cost_logger.log_run(
                agent=agent,
                model=AGENT_DEFAULT_MODEL.get(agent, "unknown"),
                prompt=fix_prompt,
                output=fix_output,
                prd_name="N/A",
                iteration=i,
                phase="coverage_fix",
                purpose="fixing_coverage_regressions",
            )

        new_report, new_cov = get_coverage_report(caffeinate=caffeinate)
        logger.info(f"New Total Coverage: {new_cov}%")

        if new_cov > current_cov:
            logger.info(f"✅ Coverage improved by {new_cov - current_cov}%!")
        else:
            logger.info("❌ Coverage did not improve in this iteration.")

        if COMPLETION_PROMISE in output:
            logger.info("Agent signaled completion.")

        if new_cov > current_cov and test_exit_code == 0:
            logger.info("Committing improvements...")
            run_command(["git", "add", "."], caffeinate=caffeinate)
            run_command(
                [
                    "git",
                    "commit",
                    "-m",
                    f"Improve test coverage from {current_cov}% to {new_cov}%",
                ],
                caffeinate=caffeinate,
            )

    logger.info("\n--- Coverage Improvement Loop Finished ---")
