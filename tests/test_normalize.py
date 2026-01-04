import pytest
import pathlib
from unittest.mock import patch, MagicMock
from vibe_tools.normalize import normalize_prd

def test_normalize_prd_no_files(tmp_path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    prds_dir = tmp_path / "prds"
    prds_dir.mkdir()
    
    with patch("vibe_tools.normalize.PRDS_DIR", prds_dir):
        with patch("vibe_tools.normalize.DEFAULT_SPECS_DIR", specs_dir):
            with patch("vibe_tools.normalize.PROMPTS_DIR", tmp_path / "prompts"):
                (tmp_path / "prompts").mkdir()
                (tmp_path / "prompts" / "pdr_normalization_prompt.txt").write_text("prompt")
                
                normalize_prd(agent="cursor-agent")
                # No files found should return early
                assert len(list(prds_dir.glob("*.yaml"))) == 0

def test_normalize_prd_with_file(tmp_path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "prd_01_test.md").write_text("human prd")
    
    prds_dir = tmp_path / "prds"
    prds_dir.mkdir()
    
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "pdr_normalization_prompt.txt").write_text("normalize {PASTE HUMAN PRD HERE}")
    
    with patch("vibe_tools.normalize.PRDS_DIR", prds_dir):
        with patch("vibe_tools.normalize.DEFAULT_SPECS_DIR", specs_dir):
            with patch("vibe_tools.normalize.PROMPTS_DIR", prompts_dir):
                with patch("vibe_tools.normalize.run_agent") as mock_agent:
                    mock_agent.return_value = ("yaml content", 0)
                    normalize_prd(agent="cursor-agent")
                    
                    mock_agent.assert_called()
                    assert (prds_dir / "prd_01_test.yaml").exists()
                    assert (prds_dir / "prd_01_test.yaml").read_text() == "yaml content"
