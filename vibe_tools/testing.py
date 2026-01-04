import pathlib
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

from vibe_tools.utils import get_changed_files, logger, run_command


class ProjectTester:
    __test__ = False

    def __init__(self, backend_root="backend", frontend_root="frontend"):
        self.backend_root = pathlib.Path(backend_root)
        self.frontend_root = pathlib.Path(frontend_root)
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

    def discover_backend_test_cmd(self):
        """Discovers the command to run backend tests."""
        if self.has_make_target("test"):
            return ["make", "test"]

        # If backend/tests does not exist, skip testing
        backend_tests = self.backend_root / "tests"
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
                ["python3", "-m", "pytest", "--version"], capture_output=True, check=True
            )
            return ["python3", "-m", "pytest", "-v", str(backend_tests)]
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return None

    def discover_frontend_test_cmd(self):
        """Discovers the command to run frontend tests."""
        if self.has_make_target("frontend-test"):
            return ["make", "frontend-test"]

        if self.frontend_root.exists() and (self.frontend_root / "package.json").exists():
            return ["npm", "--prefix", str(self.frontend_root), "test", "--", "--run"]

        return None

    def discover_frontend_lint_cmd(self):
        """Discovers the command to run frontend lint."""
        if self.has_make_target("frontend-lint"):
            return ["make", "frontend-lint"]

        if self.frontend_root.exists() and (self.frontend_root / "package.json").exists():
            return ["npm", "--prefix", str(self.frontend_root), "run", "lint"]

        return None

    def discover_coverage_cmd(self, component=None):
        """Discovers the command to run coverage for a specific component."""
        if component == "frontend":
            if self.has_make_target("frontend-coverage"):
                return ["make", "frontend-coverage"]
            if self.frontend_root.exists() and (self.frontend_root / "package.json").exists():
                return ["npm", "--prefix", str(self.frontend_root), "run", "test:coverage"] # Standard Vitest/Jest coverage
            return None

        if component == "infra":
            # Coverage for the tools themselves
            return ["pytest", "--cov=vibe_tools", "--cov-report=term-missing", "backend/tests/"]

        if component == "backend" or component is None:
            if self.has_make_target("coverage"):
                return ["make", "coverage"]
            if self.backend_root.exists():
                return ["pytest", f"--cov={self.backend_root}", "--cov-report=term-missing", f"{self.backend_root}/tests/"]

        return None

    def run_tests(self, targets=None, changed_only=False, caffeinate=False, parallel=True):
        """Runs test and lint targets, optionally filtered by changed files."""
        if targets is None:
            targets = [
                "test-backend",
                "test-frontend",
                "lint-backend",
                "lint-frontend",
            ]

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
            if self.has_make_target(target):
                logger.info(f"Running target: make {target}")
                output, code = run_command(["make", target], check=False, caffeinate=caffeinate)

                env_failure = False
                # Improved detection of command failures and environment issues
                lower_output = output.lower()
                if code == 127 or "command not found" in lower_output or "sh: " in lower_output or "not found" in lower_output:
                    # Filter out cases where the target itself says it's skipping
                    if "skipping" not in lower_output:
                        env_failure = True

                return {
                    "target": target,
                    "output": f"--- TARGET: {target} ---\n{output}",
                    "passed": code == 0,
                    "env_failure": env_failure,
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

        combined_output = "\n\n".join(outputs)
        return combined_output, all_passed, env_failures

    def _filter_targets_by_changes(self, targets, changed_files):
        """Filters targets based on which files have changed."""
        filtered = []
        
        has_backend_changes = any(
            f.startswith("backend/") or f.startswith("vibe_tools/") or f == "pyproject.toml" or f == "Makefile"
            for f in changed_files
        )
        has_frontend_changes = any(
            f.startswith("frontend/") for f in changed_files
        )

        for target in targets:
            if "backend" in target or "infra" in target or "integration" in target or "regression" in target:
                if has_backend_changes:
                    filtered.append(target)
            elif "frontend" in target:
                if has_frontend_changes:
                    filtered.append(target)
            elif target == "test" or target == "coverage":
                if has_backend_changes or has_frontend_changes:
                    filtered.append(target)
            else:
                # If we don't know, play it safe and include it
                filtered.append(target)
                
        return filtered

    def get_coverage_report(self, component=None, caffeinate=False):
        """Runs coverage for a component and returns the report and total percentage."""
        cmd = self.discover_coverage_cmd(component=component)
        if not cmd:
            return f"No coverage command discovered for component: {component or 'default'}", 0

        logger.info(f"Running Coverage ({component or 'default'}): {' '.join(cmd)}")
        output, _ = run_command(cmd, check=False, caffeinate=caffeinate)

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
