from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def silence_vibe_side_effects():
    # Patch setup_logging in both utils (source) and cli (usage)
    # Patch finalize_cost_report in both cost (source) and cli (usage)
    with patch("vibe_tools.utils.setup_logging"), \
         patch("vibe_tools.cli.setup_logging"), \
         patch("vibe_tools.cost.CostLogger._log_to_csv"), \
         patch("vibe_tools.cost.CostLogger._log_to_google"), \
         patch("vibe_tools.cost.finalize_cost_report"), \
         patch("vibe_tools.cli.finalize_cost_report"), \
         patch("atexit.register"):
        yield


@pytest.fixture(autouse=True)
def safeguard_git_operations(request):
    """
    Ensure no git operations that change state are called during testing.
    Read-only operations like 'rev-parse' or 'branch --show-current' are allowed
    if they are necessary for the project to function, but mutations are blocked.
    """
    from vibe_tools.utils import run_command as original_run_command

    forbidden_git_subcommands = {
        "checkout", "commit", "add", "reset", "merge", "push", "pull", "fetch",
        "branch", "init", "remote"
    }

    def safeguarded_run_command(cmd, *args, **kwargs):
        if isinstance(cmd, list) and len(cmd) > 0 and cmd[0] == "git":
            subcommand = cmd[1] if len(cmd) > 1 else None
            if subcommand in forbidden_git_subcommands:
                # Special case: 'git branch --show-current' or 'git rev-parse' are often used for discovery
                if subcommand == "branch" and "--show-current" in cmd:
                    pass # allow
                elif subcommand == "rev-parse":
                    pass # allow
                else:
                    raise RuntimeError(
                        f"Forbidden git mutation detected in test '{request.node.name}'! "
                        f"Command: {' '.join(cmd)}. "
                        "You must mock 'vibe_tools.utils.run_command' to prevent real git side-effects."
                    )
        
        return original_run_command(cmd, *args, **kwargs)

    with patch("vibe_tools.utils.run_command", side_effect=safeguarded_run_command):
        yield


@pytest.fixture(autouse=True)
def safeguard_llm_calls(request):
    """
    Ensure all LLM calls are mocked during testing.
    Raises RuntimeError if run_agent or _execute_dspy are called without a local mock.
    """
    # Skip safeguard for tests that specifically test these low-level functions
    if "test_run_agent" in request.node.name or "test_execute_dspy" in request.node.name:
        yield
        return

    def forbidden_call(*args, **kwargs):
        raise RuntimeError(
            f"Forbidden real LLM call detected in test '{request.node.name}'! "
            "You must mock 'vibe_tools.utils.run_agent' or 'vibe_tools.prd_writer.PRDWriter._execute_dspy' "
            "to prevent hitting real LLMs during tests."
        )

    with patch("vibe_tools.utils.run_agent", side_effect=forbidden_call), \
         patch("vibe_tools.prd_writer.PRDWriter._execute_dspy", side_effect=forbidden_call):
        yield

