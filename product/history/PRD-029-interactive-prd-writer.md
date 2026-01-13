# Interactive PRD Writer

## Overview
- **Problem statement**: Users need a guided interview process to create comprehensive PRDs from initial feature descriptions. The process should ask clarifying questions, gather requirements, and produce well-structured markdown PRDs.
- **User benefits**: Structured PRD creation process, guided interview to uncover requirements, automatic markdown generation, and integration with spec management workflow.
- **Success criteria**: PRD writer successfully conducts interviews, asks relevant questions, produces complete PRDs, and saves them in the correct location.

## Feature Inspiration
The PRD Writer (deprecated in favor of `vibe pm`) provides an interactive interview process using DSPy for question generation and an AI agent for markdown PRD creation. Users provide an initial feature description, and the system asks follow-up questions until it has enough information to generate a complete PRD.

**Key capabilities**:
- Interactive Q&A interview process
- Question generation using DSPy
- Context accumulation across interview rounds
- Satisfaction detection (when enough information gathered)
- Markdown PRD generation
- Spec file creation

## Frontend
N/A - CLI interactive prompts and Q&A.

## Backend
- **Interview Process**: Iterative Q&A loop:
  - User provides initial feature description
  - System generates follow-up questions using DSPy
  - User answers questions
  - System accumulates context
  - Process repeats until satisfaction or max rounds
- **DSPy Integration**: Uses DSPy to generate contextual questions based on:
  - Initial request
  - Accumulated context
  - Conversation history
  - Current iteration number
- **Satisfaction Detection**: DSPy signals when enough information gathered to create PRD.
- **PRD Generation**: After interview, uses AI agent (Gemini) to generate markdown PRD from:
  - Initial request
  - Complete interview log
  - PRD template structure
- **Spec File Creation**: Saves generated PRD as markdown file in `specs/` directory with appropriate naming.
- **Max Rounds**: Configurable maximum interview rounds (default: 8), prevents infinite loops.

## Infrastructure
- **DSPy Dependency**: Requires DSPy library for question generation.
- **AI Agent**: Uses configured agent (default: Gemini) for PRD generation.
- **File Storage**: Saves PRDs in `specs/` directory.

## Architecture and Constraints
- **Deprecation**: This feature is deprecated in favor of `vibe pm` interactive shell, which provides more flexibility.
- **DSPy Requirement**: Requires DSPy library, adds dependency complexity.
- **Interview Length**: Max rounds prevent overly long interviews, but may cut off before satisfaction.
- **Context Management**: Accumulates context across rounds, but may lose nuance in long interviews.

## Success Criteria
- Interview process asks relevant questions
- Satisfaction detection works correctly
- Generated PRDs are complete and well-structured
- PRDs saved in correct location with proper naming
- Process completes within max rounds for typical features

## Acceptance Tests
1. **Initial Request**: Provide feature description, verify interview starts
2. **Question Generation**: Verify relevant questions asked
3. **Context Accumulation**: Answer questions, verify context built up
4. **Satisfaction Detection**: Provide complete answers, verify satisfaction signaled
5. **PRD Generation**: Complete interview, verify PRD generated
6. **PRD Quality**: Verify generated PRD includes all required sections
7. **File Creation**: Verify PRD saved in `specs/` with correct name
8. **Max Rounds**: Test with incomplete answers, verify max rounds enforced
9. **Integration**: Verify generated PRD can be normalized and implemented

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-029
title: Interactive PRD Writer
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.015428'
updated_at: '2026-01-13T20:22:38.403866'
discussion_id: D_kwDOQzI0Lc4AjoRX
discussion_url: https://github.com/jmfk/vibe-tools/discussions/44
last_synced_at: '2026-01-13T20:22:38.403768'
sync_hash: 590266112bff48b90fc6834b117867e20625ce7ef871f459dad32fb1f12fc9f8
issue_number: null
```
</details>

<!-- vibe-id: PRD-029 -->
