---
discussion_id: D_kwDOQzI0Lc4Ajltb
discussion_url: https://github.com/jmfk/vibe-tools/discussions/38
last_synced_at: '2026-01-10T15:24:37.686211'
sync_hash: 8e76f315bcd4462bd223ccff4ed857e9c68239aefeda7acd3ee6631eed28c803
---

# Dependency Management

## Overview
- **Problem statement**: Projects need dependency checking to ensure required tools and libraries are available. The system should check for dependencies and provide helpful error messages if missing.
- **User benefits**: Dependency validation, helpful error messages, and early failure detection.
- **Success criteria**: `vibe deps` successfully checks dependencies and provides useful information about missing dependencies.

## Feature Inspiration
The `vibe deps` command checks for required dependencies (Python packages, system tools, etc.) and reports which are installed and which are missing. It provides helpful installation instructions for missing dependencies.

**Key capabilities**:
- Dependency checking
- Missing dependency detection
- Installation guidance
- Version checking (optional)

## Frontend
N/A - CLI command with formatted output.

## Backend
- **Dependency Checking**: 
  - Checks for Python packages (via import)
  - Checks for system tools (via which/command)
  - Checks for optional dependencies
- **Dependency List**: 
  - Required dependencies (must be present)
  - Optional dependencies (nice to have)
  - System tools (git, docker, etc.)
- **Reporting**: 
  - Lists installed dependencies
  - Lists missing dependencies
  - Provides installation instructions
- **Integration**: 
  - Used by other commands to validate environment
  - `check_dependencies()` function available

## Infrastructure
- **System Checks**: Uses system commands to check tools.
- **Python Checks**: Uses import to check packages.

## Architecture and Constraints
- **Check Accuracy**: May not detect all dependency issues.
- **Installation Guidance**: Provides generic guidance, may not be project-specific.

## Success Criteria
- Dependencies checked correctly
- Missing dependencies identified
- Installation guidance helpful
- Integration with commands works

## Acceptance Tests
1. **Dependency Check**: Run `vibe deps`, verify dependencies checked
2. **Missing Detection**: Remove dependency, verify detected
3. **Installation Guidance**: Verify guidance provided for missing deps
4. **Integration**: Test commands that use dependency checking