import pytest
import pathlib
from unittest.mock import patch, MagicMock
from vibe_tools.testing import ProjectTester

def test_has_make_target(tmp_path):
    makefile = tmp_path / "Makefile"
    makefile.write_text("test:\n\techo test\nlint:\n\techo lint")
    
    tester = ProjectTester()
    tester.makefile = makefile
    
    assert tester.has_make_target("test") == True
    assert tester.has_make_target("lint") == True
    assert tester.has_make_target("nonexistent") == False

def test_discover_backend_test_cmd(tmp_path):
    tester = ProjectTester()
    tester.makefile = tmp_path / "Makefile"
    
    # 1. Makefile has target
    tester.makefile.write_text("test:\n\techo test")
    assert tester.discover_backend_test_cmd() == ["make", "test"]
    
    # 2. No Makefile, but pytest in path
    tester.makefile.unlink()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert tester.discover_backend_test_cmd() == ["pytest", "-v"]

def test_discover_frontend_test_cmd(tmp_path):
    tester = ProjectTester()
    tester.makefile = tmp_path / "Makefile"
    
    # 1. Makefile has target
    tester.makefile.write_text("frontend-test:\n\techo test")
    assert tester.discover_frontend_test_cmd() == ["make", "frontend-test"]
    
    # 2. package.json exists
    tester.makefile.unlink()
    tester.frontend_root = tmp_path / "frontend"
    tester.frontend_root.mkdir()
    (tester.frontend_root / "package.json").write_text("{}")
    assert tester.discover_frontend_test_cmd() == ["npm", "--prefix", str(tester.frontend_root), "test", "--", "--run"]

def test_discover_coverage_cmd(tmp_path):
    tester = ProjectTester()
    tester.makefile = tmp_path / "Makefile"
    tester.makefile.write_text("coverage:\n\techo cov")
    assert tester.discover_coverage_cmd() == ["make", "coverage"]
    
    tester.makefile.unlink()
    tester.backend_root = tmp_path / "src"
    tester.backend_root.mkdir()
    assert tester.discover_coverage_cmd() == ["pytest", f"--cov={tester.backend_root}", "--cov-report=term-missing", "tests/"]

def test_discover_frontend_lint_cmd(tmp_path):
    tester = ProjectTester()
    tester.makefile = tmp_path / "Makefile"
    tester.makefile.write_text("frontend-lint:\n\techo lint")
    assert tester.discover_frontend_lint_cmd() == ["make", "frontend-lint"]
    
    tester.makefile.unlink()
    tester.frontend_root = tmp_path / "frontend"
    tester.frontend_root.mkdir()
    (tester.frontend_root / "package.json").write_text("{}")
    assert tester.discover_frontend_lint_cmd() == ["npm", "--prefix", str(tester.frontend_root), "run", "lint"]

def test_run_tests_with_failures(tmp_path):
    tester = ProjectTester()
    tester.makefile = tmp_path / "Makefile"
    tester.makefile.write_text("test-backend:\n\techo test\ntest-frontend:\n\techo test")
    
    with patch("vibe_tools.testing.run_command") as mock_run:
        # One pass, one fail
        mock_run.side_effect = [("pass", 0), ("fail", 1)]
        output, passed = tester.run_tests()
        assert passed == False
        assert "TARGET: test-backend" in output
        assert "TARGET: test-frontend" in output
