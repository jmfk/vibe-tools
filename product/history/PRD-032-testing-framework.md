# Testing Framework

## Overview
- **Problem statement**: Projects need testing configuration management that supports multiple test types (backend, frontend), different test runners, and integration with the development workflow. The system should discover and configure tests automatically.
- **User benefits**: Automatic test discovery, flexible test runner support, testing configuration management, and integration with coverage and test-fix loops.
- **Success criteria**: Testing framework successfully discovers tests, supports multiple test runners, manages configuration, and integrates with other tools.

## Feature Inspiration
The `vibe testing` command manages testing configuration. It discovers test infrastructure, supports multiple test runners (pytest, jest, vitest, make), and provides testing configuration that integrates with coverage and test-fix loops.

**Key capabilities**:
- Test discovery (backend, frontend)
- Test runner detection (pytest, jest, vitest, make)
- Testing configuration management
- Integration with test loops

## Frontend
N/A - CLI command.

## Backend
- **Test Discovery**: 
  - Discovers backend tests (pytest, make test)
  - Discovers frontend tests (jest, vitest, npm test)
  - Detects test directories and files
- **Test Runner Detection**: 
  - Checks for Makefile targets
  - Checks for package.json scripts
  - Checks for test runner executables
  - Falls back to standard commands
- **Configuration**: 
  - Stores test configuration in project state
  - Configures test commands per component
  - Supports custom test commands
- **Integration**: 
  - Used by coverage loop
  - Used by test-fix loop
  - Used by ProjectTester class

## Infrastructure
- **Test Infrastructure**: Integrates with existing test runners.
- **Configuration Storage**: Test config in project state.

## Architecture and Constraints
- **Test Runner Support**: Must support common test runners, may not support all.
- **Discovery Accuracy**: Test discovery may not be 100% accurate.

## Success Criteria
- Tests discovered correctly
- Test runners detected accurately
- Configuration managed properly
- Integration with loops works

## Acceptance Tests
1. **Test Discovery**: Run on project, verify tests discovered
2. **Runner Detection**: Verify test runners detected correctly
3. **Configuration**: Verify configuration saved correctly
4. **Integration**: Verify used by coverage and test-fix loops

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-032
title: Testing Framework
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.016210'
updated_at: '2026-01-17T22:40:12.082930'
discussion_id: null
discussion_url: https://github.com/jmfk/vibe-tools/discussions/47
last_synced_at: null
sync_hash: null
issue_number: null
```
</details>

<!-- vibe-id: PRD-032 -->
