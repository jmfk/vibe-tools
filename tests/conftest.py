import pytest
from unittest.mock import patch

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

