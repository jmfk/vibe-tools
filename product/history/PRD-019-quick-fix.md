---
id: PRD-019
title: Quick Fix
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.011387'
updated_at: '2026-01-13T19:03:41.673372'
discussion_id: D_kwDOQzI0Lc4AjoM8
discussion_url: https://github.com/jmfk/vibe-tools/discussions/29
last_synced_at: '2026-01-13T19:03:41.673275'
sync_hash: 57d776767df93170ec68e58171a6196b9aab66b6c657b62b7d585f17263a60db
---

# Quick Fix

## Overview
- **Problem statement**: Developers need a generic, flexible loop for quick fixes that can be applied to any problem with a custom success function and prompt builder. The system should support various fix scenarios beyond just tests.
- **User benefits**: Flexible fix mechanism for any problem type, custom success criteria, iterative refinement, and reusable fix infrastructure.
- **Success criteria**: Quick fix loop successfully applies fixes for various problem types, iterates until success, and provides flexible customization.

## Feature Inspiration
The `vibe quick-fix` command provides a generic quick-fix loop using the `QuickFixLoop` class. It takes a custom success function (determines when fix is complete) and prompt builder (generates prompts per iteration), making it suitable for any fix scenario.

**Key capabilities**:
- Generic fix loop infrastructure
- Custom success function
- Custom prompt builder
- Direct LLM calls (no agent wrapper)
- Iterative refinement
- Configurable model selection

## Frontend
N/A - CLI command, used by other commands or directly.

## Backend
- **QuickFixLoop Class**: Generic loop implementation:
  - `name`: Fix operation name
  - `success_fn`: Function returning True if fix succeeded
  - `prompt_builder`: Function taking iteration number, returning prompt
  - `max_iterations`: Maximum fix attempts
  - `model`: LLM model to use
- **Fix Process**:
  1. Check if already successful (call success_fn)
  2. If successful, exit early
  3. For each iteration:
     - Build prompt using prompt_builder(iteration)
     - Call LLM directly (run_llm)
     - Apply fixes from LLM output
     - Check success_fn()
     - If successful, exit
     - If not, continue
  4. Return success/failure
- **Direct LLM Calls**: Uses `run_llm()` directly, not agent wrapper:
  - Faster (no agent overhead)
  - More control over prompts
  - Suitable for simple fixes
- **Fix Application**: 
  - LLM output parsed for code changes
  - Changes applied to codebase
  - Success verified via success_fn
- **Use Cases**:
  - Test fixes (custom success: tests pass)
  - Lint fixes (custom success: lint passes)
  - Build fixes (custom success: build succeeds)
  - Any custom fix scenario

## Infrastructure
- **LLM Integration**: Direct calls to LLM APIs (Gemini, Claude, etc.).
- **File System**: Reads/writes code files for fixes.

## Architecture and Constraints
- **Flexibility**: Success function and prompt builder must be provided by caller.
- **LLM Dependency**: Requires LLM API access, adds latency.
- **Fix Quality**: Relies on LLM to generate correct fixes.
- **Iteration Limits**: Max iterations prevents infinite loops.

## Success Criteria
- Generic loop works for various fix types
- Success function correctly determines completion
- Prompt builder generates appropriate prompts
- Fixes applied successfully
- Iteration completes within limits

## Acceptance Tests
1. **Early Exit**: Test with already-successful state, verify early exit
2. **Success Function**: Test custom success function, verify called correctly
3. **Prompt Building**: Test prompt builder, verify prompts generated correctly
4. **Fix Application**: Test fix application, verify changes applied
5. **Iteration**: Test multiple iterations, verify progress
6. **Completion**: Test successful fix, verify loop exits
7. **Max Iterations**: Test with unfixable problem, verify max iterations enforced
8. **Model Selection**: Test different models, verify correct model used
9. **Use Cases**: Test various fix scenarios (tests, lint, build), verify all work