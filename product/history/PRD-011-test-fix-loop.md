# Test Fix Loop

## Overview
- **Problem statement**: When tests fail, developers need an automated way to fix them. The system should identify failing tests, analyze errors, apply fixes, and verify tests pass, iterating until all tests pass.
- **User benefits**: Automated test failure fixing, iterative refinement, error analysis, and integration with test infrastructure.
- **Success criteria**: Loop successfully fixes failing tests, iterates until all tests pass, handles various error types, and maintains code quality.

## Feature Inspiration
The `vibe test-fix` command runs an automated loop to fix failing tests. It runs the test suite, identifies failures, calls an AI agent with error information, applies fixes, re-runs tests, and repeats until all tests pass or max iterations reached.

**Key capabilities**:
- Test execution and failure detection
- Error analysis and reporting
- Automated fix application
- Test verification
- Iterative improvement
- State persistence (resume from last error)

## Frontend
N/A - CLI command with progress output.

## Backend
- **Test Execution**: Uses `ProjectTester`:
  - Discovers test command (make test, pytest, npm test)
  - Runs tests for backend, frontend, or both
  - Captures output and exit code
- **Failure Detection**: 
  - Exit code != 0 indicates failures
  - Parses test output for error messages
  - Identifies which tests failed
  - Extracts error details
- **Fix Loop**:
  1. Run test suite
  2. If all tests pass, exit
  3. Extract failure information
  4. Build fix prompt with errors
  5. Call AI agent to fix
  6. Apply agent's suggested fixes
  7. Re-run tests
  8. If still failing, repeat
  9. Continue until all pass or max iterations
- **State Persistence**: 
  - Saves state to `.test_fix_state.json`
  - Tracks current iteration, last error
  - Allows resuming after interruption
- **Prompt Building**: Uses `test_fix_prompt.txt`:
  - Includes test output/errors
  - Provides codebase context
  - Specifies fix requirements
- **Fix Application**: 
  - Agent suggests code changes
  - System applies changes to codebase
  - Verifies changes applied correctly
- **Fast Mode**: `--fast` flag:
  - Skips frontend tests (backend only)
  - Faster iteration for backend-focused fixes

## Infrastructure
- **Test Infrastructure**: Integrates with existing test runners.
- **State Storage**: `.test_fix_state.json` in project root.
- **Agent Integration**: Calls configured agent for fixes.

## Architecture and Constraints
- **Fix Quality**: Fixes must be correct, not just make tests pass (avoid masking issues).
- **Code Quality**: Fixes should maintain code quality, follow project patterns.
- **Iteration Limits**: Max iterations prevent infinite loops.
- **State Recovery**: State persistence allows resuming after crashes.
- **Error Types**: Must handle various error types (syntax, logic, import, etc.).

## Success Criteria
- Failing tests identified correctly
- Fixes applied successfully
- Tests pass after fixes
- Code quality maintained
- Iteration completes within limits
- State persistence works

## Acceptance Tests
1. **Test Execution**: Run on project with failing tests, verify failures detected
2. **Error Extraction**: Verify error information extracted correctly
3. **Fix Application**: Verify agent fixes applied to codebase
4. **Test Verification**: Verify tests pass after fixes
5. **Iteration**: Run multiple iterations, verify progress
6. **Completion**: Verify loop exits when all tests pass
7. **State Persistence**: Interrupt loop, resume, verify state restored
8. **Fast Mode**: Test with --fast flag, verify frontend skipped
9. **Error Handling**: Test with various error types, verify handled correctly
10. **Max Iterations**: Test with unfixable errors, verify max iterations enforced

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-011
title: Test Fix Loop
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.012843'
updated_at: '2026-01-13T20:07:27.797463'
discussion_id: null
discussion_url: https://github.com/jmfk/vibe-tools/discussions/34
last_synced_at: null
sync_hash: null
implementation_id: v01-170
implementation_yaml: v01-170_13_test_fix_loop.yaml
issue_number: null
```
</details>

<!-- vibe-id: PRD-011 -->
