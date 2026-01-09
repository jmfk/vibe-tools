# PRD: PM LLM Loop Refactor (Gemini 3 Flash & Streaming)

## Overview
- **Problem Statement**: The current `vibe pm` script relies on a standard agent call pattern that is slower and lacks real-time interactivity. Product management workflows require faster responses, streaming feedback, and the ability to manage multiple concurrent or queued thoughts.
- **User Benefits**: Instant feedback via streaming, more efficient interaction through direct Gemini 3 Flash integration (bypassing heavy agent wrappers where appropriate), and advanced control over the LLM's thought process (queuing, stopping, pushing).

## Goals
1. **Efficiency**: Refactor `vibe pm` to use a direct, high-performance LLM loop.
2. **Interactivity**: Implement real-time streaming of LLM responses.
3. **Control**: Provide "Ctrl commands" to interrupt the LLM.
4. **Queue Management**: Implement a message queue for LLM queries with support for:
    - Queuing messages while the LLM is busy.
    - Canceling queued messages.
    - "Pushing" a message to replace the current query immediately.

## Key Capabilities

### 1. Direct LLM Loop Integration
- Move from `cursor-agent` wrapper to a direct `run_llm` style loop optimized for Gemini 3 Flash.
- Use `gemini-2.0-flash-exp` (aliased as `gemini-3-flash`) for the fastest possible response times.

### 2. Streaming Response
- The interactive shell should display characters as they are received from the LLM.
- Maintain terminal styling while streaming.

### 3. Advanced Interaction Controls (Ctrl Commands)
- **Ctrl-C**: Interrupt current LLM generation.
- **Ctrl-Q**: (Optional/Configurable) Clear the current queue.
- **Stop**: Explicit command or key combo to stop the current question/response.

### 4. Message Queuing System
- **Queue**: A list of messages to be processed by the LLM in order.
- **Interruption**: If the LLM is busy, new messages are added to the queue by default.
- **Push**: A special command or flag (e.g., `/push` or a modifier) that stops the current LLM task and starts processing the new one immediately.
- **Cancellation**: Ability to view and remove items from the pending queue.

## Backend Requirements
- **Async Implementation**: The `run_loop` in `InteractivePM` needs to handle asynchronous input and LLM streaming simultaneously.
- **Queue Logic**: A robust queue manager that tracks the state of the LLM (IDLE vs. BUSY).
- **Signal Handling**: Improved signal handling to catch Ctrl-C without exiting the entire shell, instead redirecting it to stop the current LLM stream.

## Success Criteria
- LLM starts streaming responses within <1 second of command submission.
- User can successfully stop a long LLM response using a Ctrl command.
- Queued messages are executed sequentially after the previous one finishes.
- `/push` successfully interrupts the current task and starts the new one.

## Implementation Plan
1.  **Refactor `InteractivePM` to use `asyncio`**: This is necessary for non-blocking UI and background LLM processing.
2.  **Implement `StreamingLLM` client**: Create a version of `run_llm` that returns an async generator of chunks.
3.  **Create `MessageQueue` class**: Manage the FIFO queue of prompts.
4.  **Update Command Handlers**: Add `/push`, `/queue`, and handle terminal interrupts.
