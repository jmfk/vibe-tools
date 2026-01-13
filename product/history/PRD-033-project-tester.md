# Project Tester

## Overview
- **Problem statement**: The system needs a unified interface for running tests across different components (backend, frontend) and test types (unit, integration, coverage). The ProjectTester class provides this abstraction.
- **User benefits**: Unified test interface, component-aware testing, coverage support, and integration with all test-related features.
- **Success criteria**: ProjectTester successfully runs tests for all components, discovers test commands correctly, supports coverage, and integrates with all test features.

## Feature Inspiration
The `ProjectTester` class provides a unified interface for testing. It discovers test commands, runs tests for backend/frontend components, supports coverage reporting, and integrates with coverage and test-fix loops.

**Key capabilities**:
- Test command discovery
- Component-aware testing (backend, frontend, all)
- Test execution
- Coverage reporting
- Test runner abstraction

## Frontend
N/A - Class used by other components.

## Backend
- **ProjectTester Class**: 
  - `backend_root`: Backend project root
  - `frontend_root`: Frontend project root
  - Discovers and executes tests
- **Test Discovery Methods**:
  - `discover_backend_test_cmd()`: Finds backend test command
  - `discover_frontend_test_cmd()`: Finds frontend test command
  - `discover_coverage_cmd(component)`: Finds coverage command
  - `discover_frontend_lint_cmd()`: Finds frontend lint command
- **Test Execution**:
  - `run_tests(component, caffeinate, fast)`: Runs tests for component
  - Supports backend, frontend, or both
  - Fast mode skips frontend tests
- **Coverage**:
  - `get_coverage_report(component, caffeinate)`: Gets coverage report
  - Parses coverage output
  - Extracts coverage percentage
- **Makefile Support**: 
  - Checks for Makefile targets first
  - Falls back to standard commands
- **Component Detection**: 
  - Detects if frontend exists
  - Handles projects with only backend or frontend

## Infrastructure
- **Test Runners**: Integrates with pytest, jest, vitest, make.
- **Coverage Tools**: Integrates with pytest-cov, jest coverage, etc.

## Architecture and Constraints
- **Discovery Order**: Makefile → standard commands → fallbacks.
- **Component Support**: Must handle various project structures.

## Success Criteria
- Test discovery works for all components
- Test execution successful
- Coverage reporting accurate
- Integration with loops works

## Acceptance Tests
1. **Backend Tests**: Run backend tests, verify executed correctly
2. **Frontend Tests**: Run frontend tests, verify executed correctly
3. **Coverage**: Get coverage report, verify accurate
4. **Discovery**: Verify test commands discovered correctly
5. **Makefile**: Test with Makefile, verify targets used
6. **Component Detection**: Test various project structures, verify handled

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-033
title: Project Tester
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.016480'
updated_at: '2026-01-13T20:22:45.955974'
discussion_id: D_kwDOQzI0Lc4AjoRf
discussion_url: https://github.com/jmfk/vibe-tools/discussions/48
last_synced_at: '2026-01-13T20:22:45.955817'
sync_hash: 4445b882914215d99bfab6efa947eec0563e58ccff150e2dfa00f241a696b344
issue_number: null
```
</details>

<!-- vibe-id: PRD-033 -->
