import pathlib
import subprocess
import re
from vibe_tools.utils import run_command

class Tester:
    def __init__(self, backend_root="src", frontend_root="frontend"):
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
        
        # Fallback to pytest if available
        try:
            subprocess.run(["pytest", "--version"], capture_output=True, check=True)
            return ["pytest", "-v"]
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Try python3 -m pytest
        try:
            subprocess.run(["python3", "-m", "pytest", "--version"], capture_output=True, check=True)
            return ["python3", "-m", "pytest", "-v"]
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

    def discover_coverage_cmd(self):
        """Discovers the command to run coverage."""
        if self.has_make_target("coverage"):
            return ["make", "coverage"]
        
        # Default to pytest --cov if src exists
        if self.backend_root.exists():
            return ["pytest", f"--cov={self.backend_root}", "--cov-report=term-missing", "tests/"]
        
        return None

    def run_tests(self, caffeinate=False):
        """Runs tests, prioritizing 'make test' if available, otherwise discovering components."""
        if self.has_make_target("test"):
            print("Running all tests via 'make test'...")
            output, code = run_command(["make", "test"], check=False, caffeinate=caffeinate)
            return output, code == 0

        # Fallback to component discovery
        backend_cmd = self.discover_backend_test_cmd()
        frontend_lint_cmd = self.discover_frontend_lint_cmd()

        backend_output = ""
        backend_code = 0
        if backend_cmd:
            print(f"Running Backend Tests: {' '.join(backend_cmd)}")
            backend_output, backend_code = run_command(backend_cmd, check=False, caffeinate=caffeinate)
        else:
            print("No backend test command discovered.")

        frontend_output = ""
        frontend_code = 0
        if frontend_lint_cmd:
            print(f"Running Frontend Lint: {' '.join(frontend_lint_cmd)}")
            frontend_output, frontend_code = run_command(frontend_lint_cmd, check=False, caffeinate=caffeinate)
        else:
            print("No frontend lint command discovered.")

        passed = backend_code == 0 and frontend_code == 0
        combined_output = f"BACKEND TEST OUTPUT:\n{backend_output}\n\nFRONTEND LINT OUTPUT:\n{frontend_output}"
        
        return combined_output, passed

    def get_coverage_report(self, caffeinate=False):
        """Runs coverage and returns the full report and total coverage percentage."""
        cmd = self.discover_coverage_cmd()
        if not cmd:
            return "No coverage command discovered.", 0

        print(f"Running Coverage: {' '.join(cmd)}")
        output, _ = run_command(cmd, check=False, caffeinate=caffeinate)

        # Extract total coverage from the last line like 'TOTAL ... 68%'
        match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
        if match:
            total_cov = int(match.group(1))
        else:
            total_cov = 0

        return output, total_cov


