import json
import pathlib
import pytest
import re
from unittest.mock import MagicMock, patch
from vibe_tools.ralph import _implement_single_prd
from vibe_tools.prds import PRD
from vibe_tools.utils import KNOWLEDGE_DIR

@pytest.fixture
def mock_prd(tmp_path):
    prd_path = tmp_path / "PRD-999-test.md"
    prd = PRD(
        id="PRD-999",
        title="Test PRD",
        type="FEATURE",
        status="backlog",
        content="Test content",
        path=prd_path
    )
    prd.save()
    return prd

@pytest.fixture
def mock_config():
    return {
        "iterations": {"implementation": 1, "debug": 1},
        "ralph": {"review": False, "tests": False, "auto_merge": False}
    }

def test_implement_single_prd_with_memory(mock_prd, mock_config, tmp_path, monkeypatch):
    """Verify implementation loop handles short-term and global memory."""
    agent = "test-agent"
    stream = False
    
    # Setup knowledge dir
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "existing.md").write_text("Existing knowledge")
    
    monkeypatch.setattr("vibe_tools.utils.KNOWLEDGE_DIR", knowledge_dir)
    
    with patch("vibe_tools.ralph.normalize_to_data") as mock_normalize, \
         patch("vibe_tools.ralph._switch_to_branch") as mock_switch, \
         patch("vibe_tools.ralph.get_prompt") as mock_get_prompt, \
         patch("vibe_tools.ralph.get_agent_command") as mock_get_cmd, \
         patch("vibe_tools.ralph.run_agent") as mock_run_agent, \
         patch("vibe_tools.ralph.load_project_state") as mock_load_state, \
         patch("vibe_tools.ralph.save_project_state") as mock_save_state, \
         patch("vibe_tools.ralph.merge_insights") as mock_merge, \
         patch("vibe_tools.ralph.update_global_knowledge") as mock_update_global, \
         patch("vibe_tools.ralph.is_dirty", return_value=False):
        
        mock_normalize.return_value = {"CAPABILITIES": ["Test capability"]}
        # New template has more placeholders
        mock_get_prompt.return_value = "Test prompt {title} {description} {success_criteria} {global_knowledge} {short_term_memory}"
        
        # Agent response includes INSIGHTS
        mock_run_agent.return_value = ("Success <INSIGHTS>New pattern found</INSIGHTS> <promise>DONE</promise>", 0)
        mock_load_state.return_value = {"completed_prds": []}
        mock_merge.return_value = "Merged insights"
        
        # Test the implementation loop
        success = _implement_single_prd(mock_prd, agent, stream, mock_config)
        
        assert success is True
        
        # 1. Verify prompt formatting included memory context
        mock_get_cmd.assert_called_once()
        args, _ = mock_get_cmd.call_args
        prompt = args[1]
        assert "existing.md" in prompt  # From global_knowledge
        assert "No insights yet." in prompt # Initial short-term memory
        
        # 2. Verify insights were merged
        mock_merge.assert_called_once_with("", "New pattern found")
        assert mock_prd.metadata["short_term_memory"] == "Merged insights"
        
        # 3. Verify global knowledge update was triggered
        mock_update_global.assert_called_once_with("PRD-999", "Merged insights")

def test_update_global_knowledge_logic(tmp_path, monkeypatch):
    """Verify the LLM-driven categorization logic for global knowledge."""
    from vibe_tools.utils import update_global_knowledge
    
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    monkeypatch.setattr("vibe_tools.utils.KNOWLEDGE_DIR", knowledge_dir)
    
    with patch("vibe_tools.utils.run_llm") as mock_run_llm:
        # Simulate LLM returning categorized content
        mock_run_llm.return_value = "CATEGORY: Test Category\nCONTENT: Updated knowledge content"
        
        update_global_knowledge("PRD-123", "Some insights")
        
        kb_file = knowledge_dir / "Test_Category.md"
        assert kb_file.exists()
        assert kb_file.read_text() == "Updated knowledge content"

def test_merge_insights_logic(monkeypatch):
    """Verify the LLM-driven merging logic for short-term memory."""
    from vibe_tools.utils import merge_insights
    
    with patch("vibe_tools.utils.run_llm") as mock_run_llm:
        mock_run_llm.return_value = " Merged Text "
        
        result = merge_insights("Old", "New")
        
        assert result == "Merged Text"
        assert "Old" in mock_run_llm.call_args[0][0]
        assert "New" in mock_run_llm.call_args[0][0]
