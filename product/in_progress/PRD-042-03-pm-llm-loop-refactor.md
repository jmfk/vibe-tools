---
id: PRD-042
title: 03 Pm Llm Loop Refactor
type: ISSUE
status: in_progress
group: null
depends_on: []
created_at: '2026-01-13T18:53:26.305624'
updated_at: '2026-01-13T19:04:02.125214'
issue_number: 11
last_synced_at: '2026-01-13T18:53:48.926099'
sync_hash: 04a0d6768abbb673c23dc671d3c2dd950a78de95187a8650d19c63c7be7f1de6
---

# 03 Pm Llm Loop Refactor

## System Contract
### Problem Statement
  The current vibe pm script relies on a standard agent call pattern that is slower and lacks real-time interactivity.
### Performance
  LLM starts streaming responses within <1 second of command submission.
### Constraints
  - Async implementation using asyncio for non-blocking UI and background LLM processing
  - StreamingLLM client returning async generator of chunks
  - MessageQueue class tracking state (IDLE vs. BUSY)
  - Signal handling for Ctrl-C to interrupt stream without exiting shell
  - Use gemini-2.0-flash-exp (aliased as gemini-3-flash)

## Domain Model
### Classes
  {'InteractivePM': 'asyncio refactored class', 'StreamingLLM': 'async generator of chunks', 'MessageQueue': 'FIFO queue of prompts; manages IDLE vs. BUSY state'}
### Commands
  - Ctrl-C: Interrupt current LLM generation
  - Ctrl-Q: (Optional/Configurable) Clear the current queue
  - Stop: explicit command or key combo to stop current question/response
  - /push: command or flag to stop current LLM task and start processing new one immediately
  - /queue: view and remove items from pending queue

## Capabilities
- direct, high-performance LLM loop integration optimized for Gemini 3 Flash
- real-time streaming of LLM responses in interactive shell while maintaining terminal styling
- Ctrl commands to interrupt LLM
- message queuing system for processing prompts in order
- queuing messages while LLM is busy
- canceling queued messages
- pushing a message to replace current query immediately
- sequential execution of queued messages

## Output Targets
- interactive shell