import subprocess
import pathlib
import sys
import os
import json
import time

STATE_FILE = pathlib.Path(".test_fix_state.json")
MAX_ITERATIONS = 10
COMPLETION_PROMISE = "<promise>DONE</promise>"


def run_command(cmd, check=True):
    """Utility to run a command and return its output."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error running command: {' '.join(cmd)}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        return result.stdout.strip(), result.returncode
    return result.stdout.strip(), result.returncode


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


def run_cursor_agent(cmd):
    """Runs cursor-agent with a live progress indicator."""
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


def run_tests():
    """Runs backend and frontend tests."""
    print("Running Backend Tests...")
    backend_output, backend_code = run_command(["make", "test"], check=False)

    print("Running Frontend Lint...")
    frontend_output, frontend_code = run_command(["make", "frontend-lint"], check=False)

    passed = backend_code == 0 and frontend_code == 0
    combined_output = f"BACKEND TEST OUTPUT:\n{backend_output}\n\nFRONTEND LINT OUTPUT:\n{frontend_output}"

    return combined_output, passed


def main():
    print("--- Starting Test and Fix Loop ---")

    saved_state = load_state()
    start_iteration = saved_state["iteration"] if saved_state else 1
    last_error = saved_state["last_error"] if saved_state else ""

    for i in range(start_iteration, MAX_ITERATIONS + 1):
        print(f"\n[Iteration {i}/{MAX_ITERATIONS}]")

        test_output, tests_passed = run_tests()

        if tests_passed:
            print("✅ All tests and linting passed!")
            clear_state()
            break

        print("❌ Tests or linting failed. Asking Cursor Agent to fix...")

        prompt = f"""The codebase currently has test or linting failures. Please fix them.
        
ERROR OUTPUT:
{test_output}

TASK:
1. Analyze the errors provided above.
2. Fix the underlying issues in the backend (FastAPI) or frontend (React).
3. Ensure that after your changes, 'make test' and 'make frontend-lint' would pass.
4. Include {COMPLETION_PROMISE} in your response once you believe the issues are fixed.
"""

        cmd = [
            "cursor-agent",
            "--model",
            "gemini-3-flash",
            "--print",
            "--force",
            "--approve-mcps",
            prompt,
        ]

        agent_output, _ = run_cursor_agent(cmd)

        save_state(i + 1, test_output)

        if i == MAX_ITERATIONS:
            print(
                f"FAILED: Could not fix all errors within {MAX_ITERATIONS} iterations."
            )
            sys.exit(1)

    print("--- Test and Fix Loop Finished ---")


if __name__ == "__main__":
    main()
