import subprocess
import pathlib
import sys
import os
import json

PRD_DIR = pathlib.Path("prds")
BACKEND_ROOT = pathlib.Path("src")
FRONTEND_ROOT = pathlib.Path("frontend")
BASE_PROMPT_TEMPLATE = pathlib.Path("prompts/ralph_base_prompt.txt")
ARCHITECTURE = pathlib.Path("prds/architecture.yaml")
OVERVIEW = pathlib.Path("prds/project_overview.yaml")
STATE_FILE = pathlib.Path(".ralph_state.json")

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


def is_merged(branch_name):
    """Checks if a branch is merged into main."""
    _, code = run_command(
        ["git", "merge-base", "--is-ancestor", branch_name, "main"], check=False
    )
    return code == 0


def save_state(prd_name, iteration, output, context):
    """Saves the current state to a file."""
    state = {
        "prd_name": prd_name,
        "iteration": iteration,
        "output": output,
        "context": context,
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


def cursor_agent_ralph_run(
    prompt_text, prd_path, architecture_path, overview_path, backend_dir, frontend_dir
):
    """
    Calls cursor-agent with the combined prompt and context.
    """
    combined_prompt = f"""{prompt_text}

CONTEXT FILES:
- PRD: {prd_path}
- Architecture: {architecture_path}
- Project Overview: {overview_path}

TARGET DIRECTORIES:
- Backend: {backend_dir}
- Frontend: {frontend_dir}

TASK:
Process the above according to the instructions. You are responsible for BOTH the backend (FastAPI) and the frontend (React). 
Update existing files or create new ones in either directory as needed to fulfill the PRD requirements.
Include {COMPLETION_PROMISE} when you are done.
"""

    cmd = [
        "cursor-agent",
        "--model",
        "gemini-3-flash",
        "--print",
        "--force",
        "--approve-mcps",
        combined_prompt,
    ]

    output, _ = run_cursor_agent(cmd)
    return output


def run_tests():
    """Runs backend and frontend tests."""
    print("Running Backend Tests...")
    backend_output, backend_code = run_command(["make", "test"], check=False)

    # Frontend tests (if lint/test scripts exist)
    print("Running Frontend Lint...")
    frontend_output, frontend_code = run_command(["make", "frontend-lint"], check=False)

    return (
        backend_output + "\n" + frontend_output,
        backend_code == 0 and frontend_code == 0,
    )


def run_review(prd_path):
    """Asks an agent to review the changes against the PRD."""
    print("Running Agentic Review...")
    review_prompt = f"""You are a Senior Full-Stack Developer. Review the recent changes in 'src/' and 'frontend/' against the provided PRD.
    
CONTEXT:
- PRD: {prd_path}

TASK:
1. Verify all requirements in the PRD are met.
2. Check for architectural consistency.
3. Check for security or performance issues.
4. Ensure frontend and backend are correctly integrated.

If everything looks correct, respond with: <review>PASSED</review>
Otherwise, list the issues and do NOT include the pass tag.
"""
    cmd = [
        "cursor-agent",
        "--model",
        "gemini-3-flash",
        "--print",
        "--force",
        "--approve-mcps",
        review_prompt,
    ]
    output, _ = run_cursor_agent(cmd)
    return output, "<review>PASSED</review>" in output


def load_base_prompt():
    return BASE_PROMPT_TEMPLATE.read_text()


def contains_completion_promise(output):
    return COMPLETION_PROMISE in output


def make_ralph_prompt(base_prompt, iteration_output, additional_context=""):
    return f"{base_prompt}\n{additional_context}\nPREVIOUS_OUTPUT:\n{iteration_output}\n\nRespond again until you include {COMPLETION_PROMISE}."


BACKEND_ROOT.mkdir(exist_ok=True)
FRONTEND_ROOT.mkdir(exist_ok=True)

# Load existing state
saved_state = load_state()
resume_prd = saved_state["prd_name"] if saved_state else None
resume_iteration = saved_state["iteration"] if saved_state else 1

# Ensure we are on main branch
print("Ensuring we are on 'main' branch...")
run_command(["git", "checkout", "main"])

# Iterate only over numbered PRDs, excluding architecture, index, and overview
for prd_file in sorted(PRD_DIR.glob("prd_*.yaml")):
    project_name = prd_file.stem
    branch_name = f"feature/{project_name}"

    # If we are resuming, skip until we reach the resume target
    if resume_prd and project_name != resume_prd:
        print(f"Skipping {project_name} (resuming from {resume_prd})...")
        continue

    # Once we reach the resume target, we don't need to skip anymore
    resume_prd = None

    print(f"\n--- Running Ralph Loop for {project_name} ---")

    # Better "already done" check: is the branch merged into main?
    if is_merged(branch_name):
        print(f"Branch {branch_name} already merged into main. Skipping...")
        continue

    # Check if branch exists
    _, check_branch = run_command(
        ["git", "rev-parse", "--verify", branch_name], check=False
    )

    if check_branch == 0:
        print(f"Branch {branch_name} already exists. Switching to it...")
        run_command(["git", "checkout", branch_name])
    else:
        print(f"Creating and switching to branch: {branch_name}")
        run_command(["git", "checkout", "-b", branch_name])

    base_prompt = load_base_prompt()
    iteration_output = saved_state["output"] if saved_state else ""
    additional_context = saved_state["context"] if saved_state else ""
    start_iteration = resume_iteration

    # Clear saved_state once it's been consumed
    saved_state = None
    resume_iteration = 1

    success = False

    for i in range(start_iteration, MAX_ITERATIONS + 1):
        print(f"[RALPH LOOP] Iteration {i}")

        prompt_for_iteration = make_ralph_prompt(
            base_prompt, iteration_output, additional_context
        )

        output = cursor_agent_ralph_run(
            prompt_for_iteration,
            prd_file,
            ARCHITECTURE,
            OVERVIEW,
            BACKEND_ROOT,
            FRONTEND_ROOT,
        )

        # Update output for next iteration or retry
        iteration_output = output

        if contains_completion_promise(output):
            print(
                f"COMPLETION PROMISE FOUND at iteration {i}. Proceeding to Quality Gates."
            )

            # Save state before running tests in case we crash
            save_state(project_name, i, output, additional_context)

            # 1. Run Tests
            test_output, tests_passed = run_tests()
            if not tests_passed:
                print("❌ Tests failed. Feeding back to agent...")
                additional_context = (
                    f"THE PREVIOUS CHANGES CAUSED TEST FAILURES:\n{test_output}"
                )
                save_state(project_name, i + 1, output, additional_context)
                continue

            print("✅ Tests passed.")

            # 2. Run Review
            # review_output, review_passed = run_review(prd_file)
            # if not review_passed:
            #     print("❌ Review failed. Feeding back to agent...")
            #     additional_context = (
            #         f"THE PREVIOUS CHANGES FAILED CODE REVIEW:\n{review_output}"
            #     )
            #     save_state(project_name, i + 1, output, additional_context)
            #     continue

            # print("✅ Review passed.")
            success = True
            break

        # If no completion promise, save state for next iteration
        additional_context = ""
        save_state(project_name, i + 1, output, additional_context)

    if success:
        # Commit changes on the feature branch
        print(f"Committing changes for: {project_name}")
        commit_prompt = f"Git commit all changes in the repository. Group changes into reasonable, atomic commits based on their purpose. Write clear and descriptive commit messages. Context: These changes were generated for PRD {project_name} and passed all quality gates (tests and review)."
        commit_cmd = [
            "cursor-agent",
            "--model",
            "gemini-3-flash",
            "--print",
            "--force",
            "--approve-mcps",
            commit_prompt,
        ]
        run_cursor_agent(commit_cmd)

        # Switch back to main and merge
        print(f"Merging {branch_name} into main...")
        run_command(["git", "checkout", "main"])
        run_command(["git", "merge", branch_name])

        # Clear state on successful merge
        clear_state()
    else:
        print(
            f"FAILED: Did not find completion promise within {MAX_ITERATIONS} iterations."
        )
        print(f"Reverting to 'main' branch.")
        run_command(["git", "checkout", "main"])
        sys.exit(1)

print("All PRDs processed via Ralph loop successfully.")
