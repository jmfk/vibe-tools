import subprocess
import pathlib
import sys
import re
import os

MAX_ITERATIONS = 5
COMPLETION_PROMISE = "<promise>DONE</promise>"
SOURCE_DIR = "src"
TEST_DIR = "tests"


def run_command(cmd, check=True):
    """Utility to run a command and return its output."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error running command: {' '.join(cmd)}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        return result.stdout.strip(), result.returncode
    return result.stdout.strip(), result.returncode


def run_cursor_agent(cmd):
    """Runs cursor-agent with a live progress indicator."""
    import sys
    import time

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    full_output, start_time = [], time.time()
    print("\n\n", end="")
    try:
        for line in iter(process.stdout.readline, ""):
            full_output.append(line)
            elapsed = int(time.time() - start_time)
            preview = line.strip()[:80]
            sys.stdout.write(
                f"\033[2A\r\033[K⏳ Agent working ({elapsed}s)...\n\033[K{preview}"
            )
            sys.stdout.flush()
    finally:
        process.stdout.close()
        process.wait()
    sys.stdout.write("\033[2A\r\033[K\n\033[K\r\033[A")
    sys.stdout.flush()
    return "".join(full_output), process.returncode


def get_coverage_report():
    """Runs make coverage and returns the full report and total coverage percentage."""
    output, _ = run_command(["make", "coverage"], check=False)

    # Extract total coverage from the last line like 'TOTAL ... 68%'
    match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
    if match:
        total_cov = int(match.group(1))
    else:
        total_cov = 0

    return output, total_cov


def cursor_agent_run(prompt_text):
    """Calls cursor-agent with the provided prompt."""
    cmd = [
        "cursor-agent",
        "--model",
        "gemini-3-flash",
        "--print",
        "--force",
        "--approve-mcps",
        prompt_text,
    ]
    output, _ = run_cursor_agent(cmd)
    return output


def improve_coverage_loop():
    print("--- Starting Coverage Improvement Loop ---")

    for i in range(1, MAX_ITERATIONS + 1):
        report, current_cov = get_coverage_report()
        print(f"\n[Iteration {i}] Current Total Coverage: {current_cov}%")

        if current_cov >= 100:
            print("100% coverage achieved!")
            break

        target_cov = current_cov + (0.3 * (100 - current_cov))
        print(f"Targeting improvement to at least {target_cov:.1f}%")

        prompt = f"""You are in TEST COVERAGE IMPROVEMENT MODE.
        
CURRENT COVERAGE REPORT:
{report}

TASK:
Improve the test coverage of the backend implementation. 
Focus on the files with the highest number of 'Missing' lines as shown in the report.
Create new test files in 'tests/' or update existing ones to cover the missing lines.
Your goal is to increase the total coverage from {current_cov}% towards the target of {target_cov:.1f}%.

RULES:
- Do not break existing tests (run 'make test' to verify).
- Use pytest and tortoise-orm testing patterns as established in 'tests/conftest.py'.
- Work directly in the 'tests/' and 'src/' directories if needed (but primarily 'tests/').
- Once you have added/updated tests that you believe significantly improve coverage, include {COMPLETION_PROMISE} in your final response.

Output code only. No extra text.
"""

        print(f"Calling Cursor Agent to improve coverage...")
        output = cursor_agent_run(prompt)

        # Verify if tests still pass
        _, test_exit_code = run_command(["make", "test"], check=False)
        if test_exit_code != 0:
            print(
                "⚠️ Warning: Tests are failing after Cursor Agent changes! Asking agent to fix..."
            )
            fix_prompt = f"The tests are failing after your last changes. Please fix them.\n\nERROR:\n{output}"
            cursor_agent_run(fix_prompt)

        new_report, new_cov = get_coverage_report()
        print(f"New Total Coverage: {new_cov}%")

        if new_cov > current_cov:
            print(f"✅ Coverage improved by {new_cov - current_cov}%!")
        else:
            print("❌ Coverage did not improve in this iteration.")

        if COMPLETION_PROMISE in output:
            print("Agent signaled completion.")

        # Optional: commit after each successful improvement
        if new_cov > current_cov and test_exit_code == 0:
            print("Committing improvements...")
            run_command(["git", "add", "."])
            run_command(
                [
                    "git",
                    "commit",
                    "-m",
                    f"Improve test coverage from {current_cov}% to {new_cov}%",
                ]
            )

    print("\n--- Coverage Improvement Loop Finished ---")


if __name__ == "__main__":
    improve_coverage_loop()
