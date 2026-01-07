from unittest.mock import patch

from vibe_tools.normalize import normalize_prd


def test_normalize_prd_no_files(tmp_path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    prds_dir = tmp_path / "prds"
    prds_dir.mkdir()

    with patch("vibe_tools.normalize.PRD_DIR", prds_dir):
        with patch("vibe_tools.normalize.DEFAULT_SPECS_DIR", specs_dir):
            with patch("vibe_tools.normalize.get_prompt", return_value="prompt"):
                normalize_prd(agent="cursor-agent")
                # No files found should return early
                assert len(list(prds_dir.glob("*.yaml"))) == 0


def test_normalize_prd_with_file(tmp_path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "prd_01_test.md").write_text("human prd")

    prds_dir = tmp_path / "prds"
    prds_dir.mkdir()

    with patch("vibe_tools.normalize.PRD_DIR", prds_dir):
        with patch("vibe_tools.normalize.DEFAULT_SPECS_DIR", specs_dir):
            with patch("vibe_tools.normalize.get_prompt", return_value="normalize {PASTE HUMAN PRD HERE}"):
                with patch("vibe_tools.normalize.run_agent") as mock_agent:
                    with patch("vibe_tools.utils.run_command") as mock_run_utils, \
                         patch("vibe_tools.normalize.run_command") as mock_run_norm, \
                         patch("vibe_tools.ralph.run_command") as mock_run_ralph:
                        mock_run_utils.return_value = ("", 0)
                        mock_run_norm.return_value = ("", 0)
                        mock_run_ralph.return_value = ("", 0)
                        mock_agent.return_value = ("yaml content", 0)
                        normalize_prd(agent="cursor-agent")

                        mock_agent.assert_called()
                        assert (prds_dir / "prd_01_test.yaml").exists()
                        # yaml.safe_dump adds a newline and potentially "..." 
                        content = (prds_dir / "prd_01_test.yaml").read_text()
                        assert "yaml content" in content


def test_normalize_prd_recursive(tmp_path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    infra_specs_dir = specs_dir / "infra"
    infra_specs_dir.mkdir()
    (infra_specs_dir / "prd_infra_01_test.md").write_text("human infra prd")

    prds_dir = tmp_path / "prds"
    prds_dir.mkdir()

    with patch("vibe_tools.normalize.PRD_DIR", prds_dir):
        with patch("vibe_tools.normalize.DEFAULT_SPECS_DIR", specs_dir):
            # Also patch the CLI load_config which is called inside normalize_prd
            with patch("vibe_tools.cli.load_config", return_value={}):
                with patch("vibe_tools.normalize.get_prompt", return_value="normalize {PASTE HUMAN PRD HERE}"):
                    with patch("vibe_tools.normalize.run_agent") as mock_agent:
                        with patch("vibe_tools.utils.run_command") as mock_run_utils, \
                             patch("vibe_tools.normalize.run_command") as mock_run_norm, \
                             patch("vibe_tools.ralph.run_command") as mock_run_ralph:
                            mock_run_utils.return_value = ("", 0)
                            mock_run_norm.return_value = ("", 0)
                            mock_run_ralph.return_value = ("", 0)
                            mock_agent.return_value = ("yaml infra content", 0)
                            normalize_prd(agent="cursor-agent")

                            assert (prds_dir / "infra" / "prd_infra_01_test.yaml").exists()
                            content = (prds_dir / "infra" / "prd_infra_01_test.yaml").read_text()
                            assert "yaml infra content" in content


def test_normalize_prd_with_invalid_yaml_fix(tmp_path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "prd_01_invalid.md").write_text("human prd")

    prds_dir = tmp_path / "prds"
    prds_dir.mkdir()

    with patch("vibe_tools.normalize.PRD_DIR", prds_dir):
        with patch("vibe_tools.normalize.DEFAULT_SPECS_DIR", specs_dir):
            with patch("vibe_tools.normalize.get_prompt", return_value="normalize {PASTE HUMAN PRD HERE}"):
                with patch("vibe_tools.normalize.run_agent") as mock_agent:
                    with patch("vibe_tools.utils.run_command") as mock_run_utils, \
                         patch("vibe_tools.normalize.run_command") as mock_run_norm, \
                         patch("vibe_tools.ralph.run_command") as mock_run_ralph:
                        mock_run_utils.return_value = ("", 0)
                        mock_run_norm.return_value = ("", 0)
                        mock_run_ralph.return_value = ("", 0)
                        # Return invalid YAML first
                        mock_agent.return_value = ("key: : invalid", 0)
                        
                        with patch("vibe_tools.utils.run_llm") as mock_run_llm:
                            # Return fixed YAML
                            mock_run_llm.return_value = "key: fixed"
                            
                            normalize_prd(agent="cursor-agent")
                            
                            mock_run_llm.assert_called()
                            assert (prds_dir / "prd_01_invalid.yaml").exists()
                            assert "key: fixed" in (prds_dir / "prd_01_invalid.yaml").read_text()
