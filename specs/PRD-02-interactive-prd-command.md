# PRD-02: Interactive PRD Command

## Overview
- **Problem statement**: The existing `write-prd` command is too linear. It uses a fixed number of interview rounds and doesn't allow for a natural back-and-forth or easy correction of AI assumptions before the PRD is finalized. Users want a more "chat-like" experience within the terminal that guides them through PRD creation.
- **User benefits**: More control over the PRD content, better alignment with user intent through interactive clarification, and a more intuitive "slash-command" interface.
- **Success criteria**: 
    - A new `vibe prd` command is available.
    - Users can answer AI-generated questions one by one.
    - Slash commands allow generating drafts, reviewing them, and saving to disk.
    - The system maintains an internal queue of questions.

## Feature Inspiration
- The command should start by asking for a title or initial description.
- It enters a loop where it shows the current state (Title, Summary, Questions).
- The AI proposes a set of questions to fill in gaps.
- The user can answer a question, write a free-form message, or use a slash command.
- Slash commands:
    - `/generate`: Triggers the AI to write a markdown PRD draft based on the current context.
    - `/review`: Displays the latest generated draft.
    - `/save`: Finalizes the PRD and writes it to `specs/`.
    - `/add <text>`: Manually adds information to the context.
    - `/reset`: Clears the current session.
    - `/help`: Shows available commands.

## Frontend (CLI)
- Interactive terminal interface using standard input or `click.prompt`.
- Clear visual distinction between AI questions and user input.
- Support for selecting from multiple options if provided by the AI (e.g., "1) Option A, 2) Option B").

## Backend (Logic)
- `InteractivePRD` class in `vibe_tools/prd_writer.py`.
- State management for:
    - Initial Request
    - Context Summary
    - Q&A History
    - Pending Questions Queue
    - Current Draft
- Integration with `cursor-agent` or other configured agents for prompt execution.

## Infrastructure
- No new infrastructure required; uses existing LLM integration.
- Files saved to `specs/` (default) or subdirectories like `specs/infra/` or `specs/cicd/`.

## Architecture and Constraints
- Must be a single-script integration (no complex external dependencies if possible).
- Uses `prompts/prd_questions_prompt.txt` to guide question generation.
- Uses `prompts/prd_generation_prompt.txt` for the final markdown generation.

## Acceptance Tests
1. **Happy Path**: Run `vibe prd "New Feature"`, answer 3 questions, run `/generate`, run `/save`, and verify `specs/prd_02_new_feature.md` exists.
2. **Slash Command**: Run `/help` and verify all commands are listed.
3. **Manual Context**: Use `/add "User must be logged in"` and verify it's included in the next `/generate` output.
4. **Draft Review**: Run `/generate` then `/review` to see the output without saving.

