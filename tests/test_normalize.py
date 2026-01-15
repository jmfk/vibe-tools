from unittest.mock import patch
from vibe_tools.normalize import normalize_prd


def test_normalize_prd_no_files(tmp_path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()

    with patch("vibe_tools.normalize.DEFAULT_SPECS_DIR", specs_dir), \
         patch("vibe_tools.normalize.get_prompt", return_value="prompt"):
        normalize_prd()
        # Should not raise errors and should not create any files
        assert len(list(tmp_path.rglob("*.yaml"))) == 0


def test_normalize_prd_with_file(tmp_path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "prd_01_test.md").write_text("human prd")

    with patch("vibe_tools.normalize.DEFAULT_SPECS_DIR", specs_dir), \
         patch("vibe_tools.normalize.get_prompt", return_value="normalize {PASTE HUMAN PRD HERE}"), \
         patch("vibe_tools.utils.run_llm") as mock_llm:

        mock_llm.return_value = "key: yaml content"
        normalize_prd(auto_overwrite=True)

        mock_llm.assert_called()
        # IMPORTANT: Verify NO files were created on disk
        assert len(list(tmp_path.rglob("*.yaml"))) == 0


def test_normalize_prd_recursive(tmp_path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    infra_specs_dir = specs_dir / "infra"
    infra_specs_dir.mkdir()
    (infra_specs_dir / "prd_infra_01_test.md").write_text("human infra prd")

    with patch("vibe_tools.normalize.DEFAULT_SPECS_DIR", specs_dir), \
         patch("vibe_tools.cli.load_config", return_value={}), \
         patch("vibe_tools.normalize.get_prompt", return_value="normalize {PASTE HUMAN PRD HERE}"), \
         patch("vibe_tools.utils.run_llm") as mock_llm:

        mock_llm.return_value = "infra: yaml infra content"
        normalize_prd(auto_overwrite=True)

        mock_llm.assert_called()
        # Verify no files created
        assert len(list(tmp_path.rglob("*.yaml"))) == 0


def test_normalize_prd_with_invalid_yaml_fix(tmp_path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "prd_01_invalid.md").write_text("human prd")

    with patch("vibe_tools.normalize.DEFAULT_SPECS_DIR", specs_dir), \
         patch("vibe_tools.normalize.get_prompt", return_value="normalize {PASTE HUMAN PRD HERE}"), \
         patch("vibe_tools.utils.run_llm") as mock_llm:

        # Return invalid YAML first, then fixed YAML
        mock_llm.side_effect = ["key: : invalid", "key: fixed"]

        normalize_prd(input_file=specs_dir / "prd_01_invalid.md", auto_overwrite=True)

        assert mock_llm.call_count == 2
        # Verify no files created
        assert len(list(tmp_path.rglob("*.yaml"))) == 0
