import pathlib
import sys
import json


from vibe_tools.utils import (
    run_command,
    run_agent,
    get_agent_command,
    ensure_dir,
    is_merged,
)
from vibe_tools.tester import Tester

PRD_DIR = pathlib.Path("prds")
BACKEND_ROOT = pathlib.Path("src")
FRONTEND_ROOT = pathlib.Path("frontend")
PROMPTS_DIR = pathlib.Path("prompts")
BASE_PROMPT_TEMPLATE = PROMPTS_DIR / "ralph_base_prompt.txt"
REVIEW_PROMPT_TEMPLATE = PROMPTS_DIR / "review_prompt.txt"
ARCHITECTURE = pathlib.Path("prds/architecture.yaml")
OVERVIEW = pathlib.Path("prds/project_overview.yaml")
STATE_FILE = pathlib.Path(".ralph_state.json")

MAX_ITERATIONS = 10
COMPLETION_PROMISE = "<promise>DONE</promise>"


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


def run_ralph_agent(
    agent_type,
    prompt_text,
    prd_path,
    architecture_path,
    overview_path,
    backend_dir,
    frontend_dir,
    caffeinate=False,
):
    """
    Calls the configured agent with the combined prompt and context.
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

    cmd = get_agent_command(agent_type, combined_prompt)
    output, _ = run_agent(cmd, caffeinate=caffeinate)
    return output


def run_tests_logic(caffeinate=False):
    """Runs backend and frontend tests."""
    tester = Tester()
    return tester.run_tests(caffeinate=caffeinate)


def run_review_logic(agent_type, prd_path, caffeinate=False):
    """Asks an agent to review the changes against the PRD."""
    print("Running Agentic Review...")
    if not REVIEW_PROMPT_TEMPLATE.exists():
        print(
            f"Warning: Review template not found at {REVIEW_PROMPT_TEMPLATE}. Skipping review."
        )
        return "", True

    review_prompt_base = REVIEW_PROMPT_TEMPLATE.read_text()
    review_prompt = review_prompt_base.replace("{prd_path}", str(prd_path))

    cmd = get_agent_command(agent_type, review_prompt)
    output, _ = run_agent(cmd, caffeinate=caffeinate)
    return output, "<review>PASSED</review>" in output


def ralph_loop(
    agent="cursor-agent", review=False, tests=False, auto_merge=False, caffeinate=False
):
    if not PROMPTS_DIR.exists():
        print("Error: prompts directory not found. Please run 'vibe init' first.")
        sys.exit(1)

    if not PRD_DIR.exists():
        print(f"Warning: PRD directory {PRD_DIR} not found. Creating it.")
        PRD_DIR.mkdir(exist_ok=True)
        print("No PRDs found. Exiting.")
        return

    # Ensure Makefile exists if tests are enabled
    if tests and not pathlib.Path("Makefile").exists():
        print("Makefile not found. Initializing with default templates...")
        from vibe_tools.templates import TEMPLATES
        makefile_content = TEMPLATES.get("Makefile")
        if makefile_content:
            pathlib.Path("Makefile").write_text(makefile_content)
            print("✅ Created default Makefile.")
        else:
            print("Warning: Could not find Makefile template. Tests might fail if not configured.")

    ensure_dir(BACKEND_ROOT)
    ensure_dir(FRONTEND_ROOT)

    # Load existing state
    saved_state = load_state()
    resume_prd = saved_state["prd_name"] if saved_state else None
    resume_iteration = saved_state["iteration"] if saved_state else 1

    # Ensure we are on main branch
    print("Ensuring we are on 'main' branch...")
    run_command(["git", "checkout", "main"])

    # Iterate only over numbered PRDs, excluding architecture, index, and overview
    prds = sorted(PRD_DIR.glob("prd_*.yaml"))
    if not prds:
        print("No PRD files found (matching 'prd_*.yaml').")
        return

    for prd_file in prds:
        project_name = prd_file.stem
        branch_name = f"feature/{project_name}"

        # If we are resuming, skip until we reach the resume target
        if resume_prd and project_name != resume_prd:
            print(f"Skipping {project_name} (resuming from {resume_prd})...")
            continue

        # Once we reach the resume target, we don't need to skip anymore
        resume_prd = None

        print(f"\n--- Running Ralph Loop for {project_name} ---")

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

        if not BASE_PROMPT_TEMPLATE.exists():
            print(
                f"Error: Base prompt template not found at {BASE_PROMPT_TEMPLATE}. Please run 'vibe init'."
            )
            sys.exit(1)

        base_prompt = BASE_PROMPT_TEMPLATE.read_text()
        iteration_output = saved_state["output"] if saved_state else ""
        additional_context = saved_state["context"] if saved_state else ""
        start_iteration = resume_iteration

        # Clear saved_state once it's been consumed
        saved_state = None
        resume_iteration = 1

        success = False

        for i in range(start_iteration, MAX_ITERATIONS + 1):
            print(f"[RALPH LOOP] Iteration {i}")

            prompt_for_iteration = f"{base_prompt}\n{additional_context}\nPREVIOUS_OUTPUT:\n{iteration_output}\n\nRespond again until you include {COMPLETION_PROMISE}."

            output = run_ralph_agent(
                agent,
                prompt_for_iteration,
                prd_file,
                ARCHITECTURE if ARCHITECTURE.exists() else "NOT FOUND",
                OVERVIEW if OVERVIEW.exists() else "NOT FOUND",
                BACKEND_ROOT,
                FRONTEND_ROOT,
                caffeinate=caffeinate,
            )

            iteration_output = output

            if COMPLETION_PROMISE in output:
                print(
                    f"COMPLETION PROMISE FOUND at iteration {i}. Proceeding to Quality Gates."
                )
                save_state(project_name, i, output, additional_context)

                # 1. Run Tests
                if tests:
                    test_output, tests_passed = run_tests_logic(caffeinate=caffeinate)
                    if not tests_passed:
                        print("❌ Tests failed. Feeding back to agent...")
                        additional_context = (
                            f"THE PREVIOUS CHANGES CAUSED TEST FAILURES:\n{test_output}"
                        )
                        save_state(project_name, i + 1, output, additional_context)
                        continue
                    print("✅ Tests passed.")
                else:
                    print("⏩ Skipping tests as requested.")

                # 2. Run Review
                if review:
                    review_output, review_passed = run_review_logic(
                        agent, prd_file, caffeinate=caffeinate
                    )
                    if not review_passed:
                        print("❌ Review failed. Feeding back to agent...")
                        additional_context = (
                            f"THE PREVIOUS CHANGES FAILED CODE REVIEW:\n{review_output}"
                        )
                        save_state(project_name, i + 1, output, additional_context)
                        continue
                    print("✅ Review passed.")
                else:
                    print("⏩ Skipping agentic review as requested.")

                success = True
                break

            additional_context = ""
            save_state(project_name, i + 1, output, additional_context)

        if success:
            print(f"Committing changes for: {project_name}")
            commit_prompt = f"Git commit all changes in the repository. Group changes into reasonable, atomic commits based on their purpose. Write clear and descriptive commit messages. Context: These changes were generated for PRD {project_name} and passed all quality gates."
            commit_cmd = get_agent_command(agent, commit_prompt)
            run_agent(commit_cmd, caffeinate=caffeinate)

            if auto_merge:
                print(f"Merging {branch_name} into main...")
                run_command(["git", "checkout", "main"])
                run_command(["git", "merge", branch_name])
            else:
                print(f"Auto-merge is OFF. Changes remain on branch {branch_name}.")
                run_command(["git", "checkout", "main"])

            clear_state()
        else:
            print(
                f"FAILED: Did not find completion promise within {MAX_ITERATIONS} iterations."
            )
            print("Reverting to 'main' branch.")
            run_command(["git", "checkout", "main"])
            sys.exit(1)

    print("All PRDs processed successfully.")
