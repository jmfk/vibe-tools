# Memory System

## Overview
- **Problem statement**: Developers need to provide global instructions that are always sent to AI agents, ensuring consistent behavior and project-specific guidelines. The system should support multiple memories and easy management.
- **User benefits**: Global agent instructions, persistent memories, easy management, and consistent agent behavior across all operations.
- **Success criteria**: Memory system successfully stores and retrieves memories, injects them into all agent prompts, and provides easy management commands.

## Feature Inspiration
The `vibe memory` command manages global agent instructions (memories). Memories are stored in `instructions/` directory, loaded automatically, and injected into every agent prompt to ensure consistent behavior.

**Key capabilities**:
- Memory storage (text files in instructions/)
- Memory listing
- Memory deletion
- Automatic injection into agent prompts
- Multiple memories support

## Frontend
N/A - CLI commands.

## Backend
- **Memory Storage**: 
  - Stored as text files in `instructions/` directory
  - One memory per file
  - Files named by user or auto-generated
- **Memory Commands**:
  - `vibe memory <text>`: Save new memory
  - `vibe memory --list`: List all memories
  - `vibe memory --delete <idx>`: Delete memory by index
  - `vibe memory --clear`: Clear all memories
  - `vibe memory`: Save a global instruction.
- **Memory Injection**: 
  - `get_instructions_context()` loads all memory files
  - Injected into every agent prompt
  - Appended to prompt with clear markers
- **Memory Format**: 
  - Plain text files
  - No special formatting required
  - Can include markdown, code, etc.

## Infrastructure
- **File Storage**: `instructions/` directory.
- **Integration**: Loaded by agent prompt builders.

## Architecture and Constraints
- **File Format**: Plain text, no special parsing.
- **Injection**: Always injected, may increase prompt size.

## Success Criteria
- Memories saved correctly
- Memories listed accurately
- Memories deleted successfully
- Memories injected into all prompts
- Management commands work

## Acceptance Tests
1. **Save Memory**: Save memory, verify file created
2. **List Memories**: List memories, verify all shown
3. **Delete Memory**: Delete memory, verify removed
4. **Clear Memories**: Clear all, verify all deleted
5. **Injection**: Run agent command, verify memories in prompt
6. **Multiple Memories**: Save multiple, verify all injected
