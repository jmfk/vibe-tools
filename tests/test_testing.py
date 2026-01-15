import os
from unittest.mock import MagicMock, patch

from vibe_tools.testing import ProjectTester


def test_has_make_target(tmp_path):
    makefile = tmp_path / "Makefile"
    makefile.write_text("test:\n\techo test\nlint:\n\techo lint")

    tester = ProjectTester()
    tester.makefile = makefile

    assert tester.has_make_target("test")
    assert tester.has_make_target("lint")
    assert not tester.has_make_target("nonexistent")


def test_discover_backend_test_cmd(tmp_path):
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        tester = ProjectTester()
        # 1. Makefile has target
        tester.makefile.write_text("test:\n\techo test")
        assert tester.discover_backend_test_cmd() == ["make", "test"]

        # 2. No Makefile, but tests directory exists
        tester.makefile.unlink()
        (tmp_path / "tests").mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert tester.discover_backend_test_cmd() == [
                "pytest",
                "-v",
                "tests",
            ]
    finally:
        os.chdir(old_cwd)


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
    assert tester.discover_frontend_test_cmd() == [
        "npx",
        "--prefix",
        str(tester.frontend_root),
        "vitest",
        "run",
    ]


def test_discover_coverage_cmd(tmp_path):
    tester = ProjectTester()
    tester.makefile = tmp_path / "Makefile"
    tester.makefile.write_text("coverage:\n\techo cov")
    assert tester.discover_coverage_cmd() == ["make", "coverage"]

    tester.makefile.unlink()
    tester.backend_root = tmp_path
    assert tester.discover_coverage_cmd() == [
        "pytest",
        f"--cov={tester.backend_root}",
        "--cov-report=term-missing",
        "tests/",
    ]


def test_discover_frontend_lint_cmd(tmp_path):
    tester = ProjectTester()
    tester.makefile = tmp_path / "Makefile"
    tester.makefile.write_text("frontend-lint:\n\techo lint")
    assert tester.discover_frontend_lint_cmd() == ["make", "frontend-lint"]

    tester.makefile.unlink()
    tester.frontend_root = tmp_path / "frontend"
    tester.frontend_root.mkdir()
    (tester.frontend_root / "package.json").write_text("{}")
    assert tester.discover_frontend_lint_cmd() == [
        "npm",
        "--prefix",
        str(tester.frontend_root),
        "run",
        "lint",
    ]


def test_discover_tauri_test_cmd(tmp_path):
    tester = ProjectTester()
    tester.makefile = tmp_path / "Makefile"

    # 1. Makefile has target
    tester.makefile.write_text("tauri-test:\n\techo test")
    assert tester.discover_tauri_test_cmd() == ["make", "tauri-test"]

    # 2. Cargo.toml exists
    tester.makefile.unlink()
    tester.frontend_root = tmp_path / "frontend"
    tester.tauri_root = tester.frontend_root / "src-tauri"
    tester.tauri_root.mkdir(parents=True)
    (tester.tauri_root / "Cargo.toml").write_text("[package]")
    assert tester.discover_tauri_test_cmd() == [
        "cargo",
        "test",
        "--manifest-path",
        str(tester.tauri_root / "Cargo.toml"),
    ]


def test_run_tests_with_failures(tmp_path):
    tester = ProjectTester()
    tester.makefile = tmp_path / "Makefile"
    tester.makefile.write_text(
        "test-backend:\n\techo test\ntest-frontend:\n\techo test"
    )

    with patch("vibe_tools.testing.run_command") as mock_run:
        # One pass, one fail
        mock_run.side_effect = [("pass", 0), ("fail", 1)]
        output, passed, env_failures, failed_targets = tester.run_tests(
            targets=["test-backend", "test-frontend"]
        )
        assert not passed
        assert "TARGET: test-backend" in output
        assert "TARGET: test-frontend" in output
        assert "test-frontend" in failed_targets
