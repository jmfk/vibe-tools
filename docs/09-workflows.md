# Workflows

## Overview

This document describes common workflows for using vibe-tools in development. Each workflow represents a complete process from start to finish.

## Complete Development Workflow

The full development lifecycle from requirements to deployment:

```bash
# Phase 1: Planning
vibe init                    # Initialize project
vibe architect              # Define architecture
vibe pm                     # Create PRDs

# Phase 2: Normalization
vibe normalize              # Convert specs to YAML

# Phase 3: Setup
vibe setup                  # Setup project structure
vibe-setup postgres         # Configure services
vibe deps                   # Install dependencies

# Phase 4: Implementation
vibe implement              # Run implementation loops

# Phase 5: Testing
vibe testing                # Run test reconciliation
vibe test-fix               # Fix any failing tests
vibe coverage               # Improve test coverage

# Phase 6: Infrastructure
vibe infra                  # Infrastructure reconciliation

# Phase 7: Deployment
vibe deploy                 # Deploy to production
```

## Coverage Improvement Workflow

Iteratively improve test coverage using AI assistance:

```bash
# Start coverage improvement loop
vibe coverage

# Monitor progress
vibe monitor

# Check current coverage
vibe status
```

### How It Works

1. **Runs coverage report**: Gets current test coverage percentage
2. **Sets target**: Aims for 30% improvement toward 100%
3. **Calls agent**: Asks AI to add tests to improve coverage
4. **Verifies tests**: Ensures new tests pass
5. **Repeats**: Continues until target reached or max iterations

### Configuration

Set coverage targets in `implementation/config.json`:

```json
{
  "coverage_targets": {
    "backend": 85,
    "frontend": 85,
    "infra": 85
  },
  "iterations": {
    "coverage": 5
  }
}
```

## Test Fixing Workflow

Automatically fix failing tests:

```bash
# Run test fix loop
vibe test-fix

# Fast mode (only changed files)
vibe test-fix --fast
```

### How It Works

1. **Runs tests**: Executes test suite
2. **Detects failures**: Identifies failing tests
3. **Calls agent**: Asks AI to fix failing tests
4. **Re-runs tests**: Verifies fixes work
5. **Repeats**: Continues until all tests pass or max iterations

### Fast Mode

`--fast` flag only runs tests for changed files:
- More efficient for large codebases
- Faster iteration
- May miss integration issues

## Normalization Workflow

Convert human specs to machine-readable YAML:

```bash
# Normalize all specs
vibe normalize

# Normalize specific spec
vibe normalize infrastructure
vibe normalize product/01_feature.md

# Auto-overwrite existing
vibe normalize --yes

# Debug mode
vibe normalize --debug
```

### Workflow Steps

1. **Scan specs directory**: Finds all `.md` files
2. **Determine type**: Global truth vs feature PRD
3. **Create branch**: `vibe/normalize/<prd_name>`
4. **Call agent**: Converts markdown to YAML
5. **Validate YAML**: Ensures proper syntax
6. **Save to prds/**: Writes normalized YAML

### After Normalization

```bash
# Review generated YAMLs
ls implementation/prds/

# Check project state
vibe status

# Continue to implementation
vibe implement
```

## Implementation Workflow

Execute PRD implementation:

```bash
# Run implementation
vibe implement

# With streaming output
vibe implement --stream

# With caffeinate
vibe implement --caffeinate
```

### Implementation Sequence

1. **Load state**: Reads `implementation/state.json`
2. **Generate plans**: If not present, creates from PRDs
3. **For each plan**:
   - Switch to plan branch
   - Architecture Setup reconciliation
   - Infrastructure reconciliation
   - CI/CD reconciliation
   - Testing reconciliation
   - Implementation reconciliation
4. **Commit changes**: On successful completion
5. **Update state**: Marks plan as completed

### Monitoring

```bash
# In another terminal
vibe monitor

# Check status
vibe status

# View costs
vibe cost
```

## Branch Management Workflow

Manage feature branches and dependencies:

```bash
# List all branches
vibe branches

# Create feature branch
vibe branch create feature-name

# Resolve conflicts
vibe branch-resolve

# Check branch status
vibe status
```

### Branch Lineage

Branches maintain parent relationships:
- Each feature branch has a parent
- Dependencies tracked in state
- Automatic merge ordering

## PRD Lifecycle Workflow

Complete PRD lifecycle management:

```bash
# 1. Create PRD
vibe pm
# Use interactive commands to create PRD

# 2. Normalize
vibe normalize

# 3. Check status
vibe history

# 4. Implement
vibe implement

# 5. Mark implemented
vibe pm
# /focus prd_01_feature
# /implemented

# 6. Rerun if needed
vibe rerun prd_01_feature
```

## Service Setup Workflow

Configure and start local services:

```bash
# 1. List available services
vibe-servers list

# 2. Install service
vibe-servers install postgres
vibe-servers install redis

# 3. Configure connection
vibe-setup postgres
vibe-setup redis

# 4. Start services
vibe-servers start all

# 5. Verify connectivity
vibe-setup test

# 6. Check status
vibe-servers status
```

## Cost Monitoring Workflow

Track and analyze LLM costs:

```bash
# View current costs
vibe cost

# Check during implementation
vibe monitor
# Shows cost accumulation in real-time

# View detailed stats
vibe stats

# Export to Google Sheets (if configured)
# Costs automatically logged during execution
```

## Interactive Refinement Workflow

Refine specifications interactively:

```bash
# Architecture refinement
vibe architect
# /show arch
# /add Focus on scalability
# /mode AGENT
# Update architecture to use microservices
# /s

# PRD refinement
vibe pm
# /focus prd_01_feature
# Add OAuth2 support
# /s
# /mode AGENT
# /s

# Normalize changes
vibe normalize

# Re-implement
vibe implement
```

## Debugging Workflow

Debug and fix issues:

```bash
# 1. Check status
vibe status

# 2. View logs
ls implementation/logs/
tail -f implementation/logs/implement.log

# 3. Check processes
vibe ps

# 4. Kill stuck processes
vibe kill

# 5. Check branch state
git status
vibe branches

# 6. Reset if needed
vibe rerun <prd_id>
```

## Quick Fix Workflow

Quick fixes for specific issues:

```bash
# Fix specific files
vibe quick-fix --files src/models.py,src/views.py

# Fix failing tests
vibe test-fix

# Fix coverage
vibe coverage
```

## Daily Development Workflow

Typical daily workflow:

```bash
# Morning: Check status
vibe status

# Start services
vibe-servers start all

# Work on feature
vibe pm
# Create/refine PRD
vibe normalize
vibe implement

# Afternoon: Test and fix
vibe test-fix
vibe coverage

# End of day: Review
vibe cost
vibe history
vibe status
```

## Best Practices

### Workflow Efficiency

1. **Use fast mode**: `--fast` for test-fix when appropriate
2. **Monitor costs**: Check `vibe cost` regularly
3. **Incremental changes**: Normalize and implement in small batches
4. **Use interactive tools**: `vibe architect` and `vibe pm` for refinement

### Error Recovery

1. **Check status first**: `vibe status` shows current state
2. **Review logs**: Check `implementation/logs/` for details
3. **Kill stuck processes**: `vibe kill` if needed
4. **Rerun if needed**: `vibe rerun <prd_id>` to reset

### Cost Management

1. **Set budgets**: Configure `default_budget` in config
2. **Monitor during runs**: Use `vibe monitor`
3. **Review costs**: Check `vibe cost` after major operations
4. **Use cheaper agents**: Consider `cursor-agent` for routine tasks

### Branch Management

1. **Keep branches in sync**: Regular merges prevent conflicts
2. **Use automerge**: For linear development
3. **Resolve conflicts early**: Use `vibe branch-resolve`
4. **Check dependencies**: `vibe branches` shows relationships

## Troubleshooting Workflows

### Implementation Stuck

```bash
# Check processes
vibe ps

# Kill stuck agents
vibe kill

# Check branch
git status

# Reset if needed
vibe rerun <prd_id>
```

### Tests Failing

```bash
# Run test fix
vibe test-fix

# Check specific targets
vibe testing

# Review test output
make test
```

### Normalization Issues

```bash
# Debug mode
vibe normalize --debug

# Check YAML syntax
cat implementation/prds/prd_*.yaml | python -m yaml

# Re-normalize specific file
vibe normalize product/problematic.md
```

See [Troubleshooting](12-troubleshooting.md) for more help.
