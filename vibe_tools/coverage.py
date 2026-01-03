import pathlib
import sys
import re


from vibe_tools.utils import run_command, run_agent, get_agent_command
from vibe_tools.tester import Tester

PROMPTS_DIR = pathlib.Path("prompts")
COVERAGE_PROMPT_TEMPLATE = PROMPTS_DIR / "coverage_improvement_prompt.txt"
MAX_ITERATIONS = 5
COMPLETION_PROMISE = "<promise>DONE</promise>"


def get_coverage_report(caffeinate=False):
    """Runs coverage and returns the full report and total coverage percentage."""
    tester = Tester()
    return tester.get_coverage_report(caffeinate=caffeinate)


def improve_coverage_loop(agent="cursor-agent", caffeinate=False):
    print("--- Starting Coverage Improvement Loop ---")

    if not PROMPTS_DIR.exists():
        print("Error: prompts directory not found. Please run 'vibe init' first.")
        sys.exit(1)

    for i in range(1, MAX_ITERATIONS + 1):
        report, current_cov = get_coverage_report(caffeinate=caffeinate)
        print(f"\n[Iteration {i}] Current Total Coverage: {current_cov}%")

        if current_cov >= 100:
            print("100% coverage achieved!")
            break

        target_cov = current_cov + (0.3 * (100 - current_cov))
        print(f"Targeting improvement to at least {target_cov:.1f}%")

        if not COVERAGE_PROMPT_TEMPLATE.exists():
            print(
                f"Error: Coverage prompt template not found at {COVERAGE_PROMPT_TEMPLATE}. Please run 'vibe init'."
            )
            sys.exit(1)

        prompt_base = COVERAGE_PROMPT_TEMPLATE.read_text()
        prompt = (
            prompt_base.replace("{report}", report)
            .replace("{current_cov}", str(current_cov))
            .replace("{target_cov}", f"{target_cov:.1f}")
        )

        print("Calling agent to improve coverage...")
        cmd = get_agent_command(agent, prompt)
        output, _ = run_agent(cmd, caffeinate=caffeinate)

        # Verify if tests still pass
        _, test_exit_code = run_command(
            ["make", "test"], check=False, caffeinate=caffeinate
        )
        if test_exit_code != 0:
            print(
                "⚠️ Warning: Tests are failing after agent changes! Asking agent to fix..."
            )
            fix_prompt = f"The tests are failing after your last changes. Please fix them.\n\nERROR:\n{output}"
            cmd_fix = get_agent_command(agent, fix_prompt)
            run_agent(cmd_fix, caffeinate=caffeinate)

        new_report, new_cov = get_coverage_report(caffeinate=caffeinate)
        print(f"New Total Coverage: {new_cov}%")

        if new_cov > current_cov:
            print(f"✅ Coverage improved by {new_cov - current_cov}%!")
        else:
            print("❌ Coverage did not improve in this iteration.")

        if COMPLETION_PROMISE in output:
            print("Agent signaled completion.")

        if new_cov > current_cov and test_exit_code == 0:
            print("Committing improvements...")
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

    print("\n--- Coverage Improvement Loop Finished ---")
