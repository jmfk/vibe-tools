import os
import pathlib
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

from vibe_tools.utils import get_changed_files, log_large_output, logger, run_command


class ProjectTester:
    __test__ = False

    def __init__(self, backend_root=".", frontend_root="frontend"):
        self.backend_root = pathlib.Path(backend_root)
        self.frontend_root = pathlib.Path(frontend_root)
        self.tauri_root = self.frontend_root / "src-tauri"
        self.makefile = pathlib.Path("Makefile")

    def has_make_target(self, target):
        """Checks if the Makefile has a specific target."""
        if not self.makefile.exists():
            return False
        try:
            content = self.makefile.read_text()
            # Simple regex to find target followed by colon at start of line
            return bool(re.search(f"^{target}:", content, re.MULTILINE))
        except Exception:
            return False

    def discover_backend_fix_cmd(self):
        """Discovers the command to run backend auto-fixes."""
        if self.has_make_target("fix-backend") or self.has_make_target("fix"):
            return (
                ["make", "fix-backend"]
                if self.has_make_target("fix-backend")
                else ["make", "fix"]
            )

        # Fallback to ruff if available
        try:
            subprocess.run(["ruff", "--version"], capture_output=True, check=True)
            return ["ruff", "check", "--fix", "."]
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return None

    def discover_frontend_fix_cmd(self):
        """Discovers the command to run frontend auto-fixes."""
        if self.has_make_target("frontend-fix"):
            return [["make", "frontend-fix"]]

        if (
            self.frontend_root.exists()
            and (self.frontend_root / "package.json").exists()
        ):
            # We run multiple commands to ensure both eslint and stylelint are fixed
            # because 'npm run lint -- --fix' might only pass --fix to the last command.
            return [
                ["npx", "--prefix", str(self.frontend_root), "eslint", ".", "--ext", "ts,tsx", "--fix"],
                ["npx", "--prefix", str(self.frontend_root), "stylelint", "src/**/*.css", "--fix"]
            ]

        return None

    def discover_tauri_fix_cmd(self):
        """Discovers the command to run tauri auto-fixes."""
        if self.has_make_target("tauri-fix"):
            return [["make", "tauri-fix"]]

        if self.tauri_root.exists() and (self.tauri_root / "Cargo.toml").exists():
            return [[
                "cargo",
                "clippy",
                "--fix",
                "--allow-dirty",
                "--manifest-path",
                str(self.tauri_root / "Cargo.toml"),
            ]]

        return None

    def run_fixes(self, components=None):
        """Runs auto-fix commands for specified components."""
        if components is None:
            components = ["backend", "frontend", "tauri"]

        results = []
        for component in components:
            cmds = None
            if component == "backend":
                found = self.discover_backend_fix_cmd()
                cmds = [found] if found and isinstance(found[0], str) else found
            elif component == "frontend":
                cmds = self.discover_frontend_fix_cmd()
            elif component == "tauri":
                cmds = self.discover_tauri_fix_cmd()

            if cmds:
                for cmd in cmds:
                    logger.info(f"🔧 Running auto-fixes for {component}: {' '.join(cmd)}")
                    output, code = run_command(cmd, check=False)
                    results.append({"component": component, "command": ' '.join(cmd), "output": output, "success": code == 0})
            else:
                logger.debug(f"No auto-fix command found for {component}")

        return results

    def discover_backend_test_cmd(self):
        """Discovers the command to run backend tests."""
        if self.has_make_target("test"):
            return ["make", "test"]

        # If tests directory does not exist, skip testing
        backend_tests = pathlib.Path("tests")
        if not backend_tests.exists():
            return None

        # Fallback to pytest if available
        try:
            subprocess.run(["pytest", "--version"], capture_output=True, check=True)
            return ["pytest", "-v", str(backend_tests)]
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Try python3 -m pytest
        try:
            subprocess.run(
                ["python3", "-m", "pytest", "--version"],
                capture_output=True,
                check=True,
            )
            return ["python3", "-m", "pytest", "-v", str(backend_tests)]
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return None

    def discover_frontend_test_cmd(self):
        """Discovers the command to run frontend tests."""
        if self.has_make_target("frontend-test"):
            return ["make", "frontend-test"]

        if (
            self.frontend_root.exists()
            and (self.frontend_root / "package.json").exists()
        ):
            return ["npx", "--prefix", str(self.frontend_root), "vitest", "run"]

        return None

    def discover_tauri_test_cmd(self):
        """Discovers the command to run tauri (Rust) tests."""
        if self.has_make_target("tauri-test"):
            return ["make", "tauri-test"]

        if self.tauri_root.exists() and (self.tauri_root / "Cargo.toml").exists():
            # Run cargo test in the tauri directory
            return [
                "cargo",
                "test",
                "--manifest-path",
                str(self.tauri_root / "Cargo.toml"),
            ]

        return None

    def discover_backend_lint_cmd(self):
        """Discovers the command to run backend lint."""
        if self.has_make_target("lint-backend") or self.has_make_target("lint"):
            return (
                ["make", "lint-backend"]
                if self.has_make_target("lint-backend")
                else ["make", "lint"]
            )

        # Fallback to ruff if available
        try:
            subprocess.run(["ruff", "--version"], capture_output=True, check=True)
            return ["ruff", "check", "vibe_tools", "tests"]
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return None

    def discover_frontend_lint_cmd(self):
        """Discovers the command to run frontend lint."""
        if self.has_make_target("frontend-lint"):
            return ["make", "frontend-lint"]

        if (
            self.frontend_root.exists()
            and (self.frontend_root / "package.json").exists()
        ):
            return ["npm", "--prefix", str(self.frontend_root), "run", "lint"]

        return None

    def discover_tauri_lint_cmd(self):
        """Discovers the command to run tauri lint (clippy)."""
        if self.has_make_target("tauri-lint"):
            return ["make", "tauri-lint"]

        if self.tauri_root.exists() and (self.tauri_root / "Cargo.toml").exists():
            return [
                "cargo",
                "clippy",
                "--manifest-path",
                str(self.tauri_root / "Cargo.toml"),
                "--",
                "-D",
                "warnings",
            ]

        return None

    def discover_frontend_build_cmd(self):
        """Discovers the command to build the frontend."""
        if self.has_make_target("build-frontend"):
            return ["make", "build-frontend"]

        if (
            self.frontend_root.exists()
            and (self.frontend_root / "package.json").exists()
        ):
            return ["npm", "--prefix", str(self.frontend_root), "run", "build"]

        return None

    def discover_tauri_build_cmd(self):
        """Discovers the command to build tauri core."""
        if self.has_make_target("build-tauri"):
            return ["make", "build-tauri"]

        if self.tauri_root.exists() and (self.tauri_root / "Cargo.toml").exists():
            return [
                "cargo",
                "build",
                "--manifest-path",
                str(self.tauri_root / "Cargo.toml"),
            ]

        return None

    def discover_coverage_cmd(self, component=None):
        """Discovers the command to run coverage for a specific component."""
        if component == "frontend":
            if self.has_make_target("frontend-coverage"):
                return ["make", "frontend-coverage"]
            if (
                self.frontend_root.exists()
                and (self.frontend_root / "package.json").exists()
            ):
                return [
                    "npm",
                    "--prefix",
                    str(self.frontend_root),
                    "run",
                    "test:coverage",
                ]  # Standard Vitest/Jest coverage
            return None

        if component == "infra":
            # Coverage for the tools themselves
            return ["pytest", "--cov=vibe_tools", "--cov-report=term-missing", "tests/"]

        if component == "backend" or component is None:
            if self.has_make_target("coverage"):
                return ["make", "coverage"]
            if self.backend_root.exists():
                return [
                    "pytest",
                    f"--cov={self.backend_root}",
                    "--cov-report=term-missing",
                    "tests/",
                ]

        return None

    def is_frontend_target(self, target):
        """Returns True if the target is related to the frontend."""
        return "frontend" in target.lower()

    def is_backend_target(self, target):
        """Returns True if the target is related to the backend or generic."""
        # Generic 'test' or 'lint' or 'coverage' are usually backend-first in this project
        # or we treat them as BE if not explicitly FE.
        if self.is_frontend_target(target):
            return False
        return True

    def is_coverage_failure(self, output):
        """Checks if the output indicates a failure due to low coverage."""
        # Common coverage failure patterns
        patterns = [
            r"Required test coverage of \d+% not reached",
            r"FAIL Required coverage not met",
            r"coverage: \d+\.\d+% is less than \d+%",
        ]
        for pattern in patterns:
            if re.search(pattern, output, re.IGNORECASE):
                return True
        return False

    def get_summary(self, failed_targets):
        """Returns a concise summary string of failed targets."""
        if not failed_targets:
            return "No targets failed."
        return f"Targets failed: {', '.join(failed_targets)}"

    def parse_failures(self, output):
        """Parses test output to extract individual failing test identifiers."""
        failures = []

        # Pytest failures usually look like:
        # FAILED tests/test_file.py::test_function - AssertionError: ...
        # Or in summary:
        # _________________________ test_function __________________________
        pytest_matches = re.findall(r"FAILED\s+(tests/[^\s:]+::[^\s]+)", output)
        failures.extend([{"id": m, "type": "backend"} for m in pytest_matches])

        # Vitest failures
        # Example: ❯ src/components/workflow/SearchHeader.test.tsx > SearchHeader > should render correctly
        # Example: FAIL  frontend/src/components/workflow/SearchHeader.test.tsx > SearchHeader > should render correctly
        vitest_matches = re.findall(
            r"(?:FAIL|❯)\s+([^\s]+\.test\.[jt]sx?)(?:\s+>\s+(.+))?", output
        )
        failures.extend(
            [
                {
                    "id": f"{m[0]} - {m[1] if m[1] else 'Unknown Test'}",
                    "file": m[0],
                    "name": m[1] if m[1] else "",
                    "type": "frontend",
                }
                for m in vitest_matches
            ]
        )

        # Cargo (Tauri) failures
        # Example: test tests::some_test ... FAILED
        cargo_matches = re.findall(r"test\s+([^\s]+)\s+\.\.\.\s+FAILED", output)
        failures.extend([{"id": m, "name": m, "type": "tauri"} for m in cargo_matches])

        return failures

    def run_single_test(self, failure):
        """Runs a single failing test."""
        if failure["type"] == "backend":
            test_id = failure["id"]
            logger.info(f"Running single backend test: {test_id}")
            # Use PYTHONPATH=. pytest -v <test_id>
            cmd = ["pytest", "-v", test_id]
            env = os.environ.copy()
            env["PYTHONPATH"] = "."
            # Since run_command doesn't take env, we'll prefix it if needed or just rely on current process env
            # Actually run_command uses subprocess.run which inherits env.
            # Let's use the same pattern as discover_backend_test_cmd but targeted.
            output, code = run_command(
                ["python3", "-m", "pytest", "-v", test_id], check=False
            )
            log_large_output(f"test_backend_{test_id}", output)
            return output, code == 0
        elif failure["type"] == "frontend":
            test_file = failure["file"]
            test_name = failure["name"]
            logger.info(f"Running single frontend test: {test_name} in {test_file}")
            # cd frontend && npx vitest run <test_file> -t "<test_name>"
            # We can use the prefix option for npm/npx
            cmd = [
                "npx",
                "--prefix",
                str(self.frontend_root),
                "vitest",
                "run",
                test_file,
                "-t",
                test_name,
            ]
            output, code = run_command(cmd, check=False)
            log_large_output(f"test_frontend_{test_name}", output)
            return output, code == 0
        elif failure["type"] == "tauri":
            test_name = failure["name"]
            logger.info(f"Running single tauri test: {test_name}")
            # cargo test --manifest-path frontend/src-tauri/Cargo.toml -- <test_name>
            cmd = [
                "cargo",
                "test",
                "--manifest-path",
                str(self.tauri_root / "Cargo.toml"),
                "--",
                test_name,
            ]
            output, code = run_command(cmd, check=False)
            log_large_output(f"test_tauri_{test_name}", output)
            return output, code == 0

        return "Unknown test type", False

    def run_tests(self, targets=None, changed_only=False, parallel=False, bypass_safety=False):
        """Runs test and lint targets, optionally filtered by changed files."""
        # Force parallel=False by default for debugging loops to keep output clean
        if targets is None:
            targets = [
                "test-backend",
                "test-frontend",
                "test-tauri",
                "lint-backend",
                "lint-frontend",
                "lint-tauri",
            ]

        # Inject CI=true to prevent interactive hangs
        env = os.environ.copy()
        env["CI"] = "true"
        env["VITE_CI"] = "true"

        if changed_only:
            changed_files = get_changed_files()
            if changed_files:
                targets = self._filter_targets_by_changes(targets, changed_files)
                logger.info(f"Filtered targets based on changes: {', '.join(targets)}")
            else:
                logger.info("No changes detected, skipping tests.")
                return "No changes detected.", True, []

        if not targets:
            return "No relevant tests to run.", True, []

        def run_target(target):
            cmd = None
            if self.has_make_target(target):
                logger.info(f"Running target: make {target}")
                cmd = ["make", target]
            else:
                # Try discovery
                if target == "test-backend" or target == "test":
                    cmd = self.discover_backend_test_cmd()
                elif target == "test-frontend":
                    cmd = self.discover_frontend_test_cmd()
                elif target == "test-tauri":
                    cmd = self.discover_tauri_test_cmd()
                elif target == "lint-backend" or target == "lint":
                    cmd = self.discover_backend_lint_cmd()
                elif target == "lint-frontend":
                    cmd = self.discover_frontend_lint_cmd()
                elif target == "lint-tauri":
                    cmd = self.discover_tauri_lint_cmd()
                elif target == "build-frontend":
                    cmd = self.discover_frontend_build_cmd()
                elif target == "build-tauri":
                    cmd = self.discover_tauri_build_cmd()
                elif target == "coverage":
                    cmd = self.discover_coverage_cmd()

            if cmd:
                logger.info(f"Running command: {' '.join(cmd)}")
                # We need to pass the env to subprocess.run.
                original_env = os.environ.copy()
                try:
                    os.environ["CI"] = "true"
                    os.environ["VITE_CI"] = "true"
                    output, code = run_command(
                        cmd, check=False, bypass_safety=bypass_safety, timeout=300
                    )
                finally:
                    # Restore original env
                    for k in ["CI", "VITE_CI"]:
                        if k in original_env:
                            os.environ[k] = original_env[k]
                        else:
                            os.environ.pop(k, None)

                log_large_output(f"test_target_{target}", output)

                env_failure = False
                # Improved detection of command failures and environment issues
                lower_output = output.lower()
                tool_missing_indicators = {
                    "command not found": "The command was not found in the shell.",
                    "not found": "A tool or file was not found.",
                    "no module named": "A Python module is missing.",
                    "sh: ": "Shell command error.",
                    "pyenv: ": "Pyenv environment error.",
                    "git safety violation": "Git has uncommitted changes blocking execution.",
                }

                detected_reason = None
                for indicator, reason in tool_missing_indicators.items():
                    if indicator in lower_output:
                        if "skipping" not in lower_output:
                            if code != 0 or indicator == "no module named":
                                env_failure = True
                                detected_reason = reason
                                break

                return {
                    "target": target,
                    "output": f"--- TARGET: {target} ---\n{output}",
                    "passed": code == 0,
                    "env_failure": env_failure,
                    "env_reason": detected_reason,
                }
            else:
                return {
                    "target": target,
                    "output": f"--- TARGET: {target} (NOT FOUND) ---",
                    "passed": True,
                    "env_failure": False,
                }

        results = []
        if parallel and len(targets) > 1:
            with ThreadPoolExecutor(max_workers=min(len(targets), 4)) as executor:
                results = list(executor.map(run_target, targets))
        else:
            for target in targets:
                results.append(run_target(target))

        outputs = [r["output"] for r in results]
        all_passed = all(r["passed"] for r in results)
        env_failures = [r["target"] for r in results if r["env_failure"]]
        failed_targets = [
            r["target"] for r in results if not r["passed"] and not r["env_failure"]
        ]

        combined_output = "\n\n".join(outputs)
        return combined_output, all_passed, env_failures, failed_targets

    def _filter_targets_by_changes(self, targets, changed_files):
        """Filters targets based on which files have changed."""
        filtered = []

        has_backend_changes = any(
            f.startswith("vibe_tools/")
            or f == "pyproject.toml"
            or f == "Makefile"
            or f.startswith("tests/")
            for f in changed_files
        )
        has_frontend_changes = any(
            f.startswith("frontend/") and not f.startswith("frontend/src-tauri/")
            for f in changed_files
        )
        has_tauri_changes = any(
            f.startswith("frontend/src-tauri/") for f in changed_files
        )

        for target in targets:
            if (
                "backend" in target
                or "infra" in target
                or "integration" in target
                or "regression" in target
            ):
                if has_backend_changes:
                    filtered.append(target)
            elif "frontend" in target:
                if has_frontend_changes:
                    filtered.append(target)
            elif "tauri" in target:
                if has_tauri_changes:
                    filtered.append(target)
            elif target == "test" or target == "coverage" or target == "build":
                if has_backend_changes or has_frontend_changes or has_tauri_changes:
                    filtered.append(target)
            else:
                # If we don't know, play it safe and include it
                filtered.append(target)

        return filtered

    def get_coverage_report(self, component=None):
        """Runs coverage for a component and returns the report and total percentage."""
        cmd = self.discover_coverage_cmd(component=component)
        if not cmd:
            return (
                f"No coverage command discovered for component: {component or 'default'}",
                0,
            )

        logger.info(f"Running Coverage ({component or 'default'}): {' '.join(cmd)}")
        output, _ = run_command(cmd, check=False)

        # Extract total coverage from the last line like 'TOTAL ... 68%'
        # This works for both pytest-cov and vitest (standard istanbul report)
        match = re.search(r"TOTAL\s+.*?\s+(\d+)%", output)
        if not match:
            # Fallback for vitest table format if it's different
            match = re.search(r"All files\s+.*?\s+(\d+)\s+", output)

        if match:
            total_cov = int(match.group(1))
        else:
            total_cov = 0

        return output, total_cov
