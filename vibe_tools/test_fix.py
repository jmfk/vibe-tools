import pathlib
import sys
import json
import click
from vibe_tools.utils import run_command, run_agent, get_agent_command

STATE_FILE = pathlib.Path(".test_fix_state.json")
PROMPTS_DIR = pathlib.Path("prompts")
TEST_FIX_PROMPT_TEMPLATE = PROMPTS_DIR / "test_fix_prompt.txt"
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

def run_tests():
    """Runs backend and frontend tests."""
    print("Running Backend Tests...")
    backend_output, backend_code = run_command(["make", "test"], check=False)

    print("Running Frontend Lint...")
    frontend_output, frontend_code = run_command(["make", "frontend-lint"], check=False)

    passed = backend_code == 0 and frontend_code == 0
    combined_output = f"BACKEND TEST OUTPUT:\n{backend_output}\n\nFRONTEND LINT OUTPUT:\n{frontend_output}"

    return combined_output, passed

def test_fix_loop(agent="cursor-agent"):
    print("--- Starting Test and Fix Loop ---")
    
    if not PROMPTS_DIR.exists():
        print("Error: prompts directory not found. Please run 'vibe init' first.")
        sys.exit(1)

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

        print(f"❌ Tests or linting failed. Asking {agent} to fix...")

        if not TEST_FIX_PROMPT_TEMPLATE.exists():
            print(f"Error: Test fix prompt template not found at {TEST_FIX_PROMPT_TEMPLATE}. Please run 'vibe init'.")
            sys.exit(1)
            
        prompt_base = TEST_FIX_PROMPT_TEMPLATE.read_text()
        prompt = prompt_base.replace("{test_output}", test_output)

        cmd = get_agent_command(agent, prompt)
        agent_output, _ = run_agent(cmd)

        save_state(i + 1, test_output)

        if i == MAX_ITERATIONS:
            print(f"FAILED: Could not fix all errors within {MAX_ITERATIONS} iterations.")
            sys.exit(1)

    print("--- Test and Fix Loop Finished ---")
