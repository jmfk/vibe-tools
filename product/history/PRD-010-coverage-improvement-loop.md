---
id: PRD-010
title: Coverage Improvement Loop
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.008767'
updated_at: '2026-01-13T18:59:05.076832'
discussion_id: D_kwDOQzI0Lc4AjltJ
discussion_url: https://github.com/jmfk/vibe-tools/discussions/22
last_synced_at: '2026-01-13T18:59:05.076728'
sync_hash: df49950c4c0dffa611f984047d8108a0e76884a8be8f9f25cabebd6170a21c77
implementation_id: v01-160
implementation_yaml: v01-160_12_coverage_improvement_loop.yaml
---

# Coverage Improvement Loop

## Overview
- **Problem statement**: Projects need automated test coverage improvement. The system should analyze current coverage, identify gaps, generate tests, and iteratively improve coverage until targets are met.
- **User benefits**: Automated test coverage improvement, iterative refinement, target-based goals, and integration with existing test infrastructure.
- **Success criteria**: Loop successfully improves test coverage, reaches target percentages, generates valid tests, and maintains test suite health.

## Feature Inspiration
The `vibe coverage` command runs an automated loop to improve test coverage. It starts by measuring current coverage, sets improvement targets (30% of remaining gap per iteration), calls an AI agent to generate tests, verifies tests pass, measures new coverage, and repeats until target coverage or max iterations reached.

**Key capabilities**:
- Coverage measurement (backend, frontend, or both)
- Target calculation (aggressive improvement targets)
- Test generation via AI agent
- Test verification (ensure new tests pass)
- Iterative improvement
- Progress tracking

## Frontend
N/A - CLI command with progress output.

## Backend
- **Coverage Measurement**: Uses `ProjectTester.get_coverage_report()`:
  - Discovers coverage command (make coverage, pytest --cov, npm test:coverage)
  - Runs coverage for specified component (backend, frontend, or all)
  - Parses coverage report
  - Extracts total coverage percentage
- **Target Calculation**: 
  - Current coverage: `current_cov`
  - Target coverage: `current_cov + (0.3 * (100 - current_cov))`
  - Aggressive: aims for 30% of remaining gap per iteration
- **Improvement Loop**:
  1. Measure current coverage
  2. If coverage >= 100%, exit
  3. Calculate target coverage
  4. Build improvement prompt with coverage report
  5. Call AI agent to generate tests
  6. Verify tests pass (run test suite)
  7. If tests fail, ask agent to fix
  8. Measure new coverage
  9. If improved, continue; if not, may exit
  10. Repeat until target or max iterations
- **Prompt Building**: Uses `coverage_improvement_prompt.txt`:
  - Includes current coverage report
  - Specifies target coverage
  - Provides context about codebase
- **Test Verification**: After agent changes, runs test suite to ensure:
  - New tests pass
  - Existing tests still pass
  - No regressions introduced
- **Cost Tracking**: Logs all agent calls for cost tracking.

## Infrastructure
- **Test Infrastructure**: Integrates with existing test runners (pytest, jest, vitest, make).
- **Coverage Tools**: Uses project's coverage tools (pytest-cov, jest coverage, etc.).
- **Agent Integration**: Calls configured agent for test generation.

## Architecture and Constraints
- **Test Quality**: Generated tests must be meaningful, not just coverage padding.
- **Test Maintenance**: Tests should be maintainable, follow project patterns.
- **Regression Prevention**: New tests must not break existing functionality.
- **Iteration Limits**: Max iterations prevent infinite loops.
- **Component Support**: Must support backend, frontend, and combined coverage.

## Success Criteria
- Coverage improves over iterations
- Generated tests are valid and meaningful
- Test suite remains healthy (all tests pass)
- Target coverage reached or max iterations hit
- Progress clearly communicated

## Acceptance Tests
1. **Coverage Measurement**: Run on project, verify coverage measured correctly
2. **Target Calculation**: Verify target calculation correct (30% of gap)
3. **Test Generation**: Verify agent generates valid tests
4. **Test Verification**: Verify new tests pass, existing tests still pass
5. **Iteration**: Run multiple iterations, verify coverage improves
6. **Completion**: Verify loop exits at 100% coverage or max iterations
7. **Component Selection**: Test with backend, frontend, all components
8. **Error Handling**: Test with failing tests, verify error handling
9. **Cost Tracking**: Verify agent calls logged for cost tracking