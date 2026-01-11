---
discussion_id: D_kwDOQzI0Lc4AjltU
discussion_url: https://github.com/jmfk/vibe-tools/discussions/32
last_synced_at: '2026-01-10T15:24:27.672577'
sync_hash: 35068d960c99698d21bbeaefc6a996c7415fd1627c43df848535c311aa9ff78c
---

# Cost Tracking System

## Overview
- **Problem statement**: Teams need to track LLM API costs across all agent operations. The system should estimate token usage, calculate costs based on model pricing, log all operations, and provide cost reporting.
- **User benefits**: Comprehensive cost tracking, token estimation, cost calculation, CSV logging, and cost reporting for budget management.
- **Success criteria**: System accurately tracks all LLM costs, estimates tokens correctly, calculates costs accurately, logs to CSV, and provides useful cost reports.

## Feature Inspiration
The cost tracking system logs all LLM API calls, estimates token usage, calculates costs based on model pricing, and stores records in CSV format. It integrates with all agent operations, provides real-time cost feedback, and supports session-level cost reporting.

**Key capabilities**:
- Token estimation (input and output)
- Cost calculation per model
- CSV logging of all operations
- Session cost tracking
- Cost reporting (`vibe cost` command)
- Model pricing database

## Frontend
N/A - CLI command for cost reporting.

## Backend
- **CostLogger Class**: Main cost tracking implementation:
  - `estimate_tokens(text)`: Estimates token count (~4 chars per token)
  - `calculate_cost(model, input_tokens, output_tokens)`: Calculates cost based on pricing
  - `log_run(...)`: Logs a single agent run with all details
- **Token Estimation**: 
  - Simple heuristic: ~4 characters per token
  - Estimates input and output tokens separately
  - Used for cost calculation
- **Pricing Database**: `PRICING` dictionary with per-model pricing:
  - Format: `{"model": {"input": price_per_1M, "output": price_per_1M}}`
  - Models: gemini-3-flash, gemini-1.5-flash, claude-3-5-sonnet, claude-3-opus, gpt-4o, gpt-4o-mini
  - Prices in USD per 1M tokens
- **Cost Calculation**: 
  - Input cost: `(input_tokens / 1_000_000) * pricing["input"]`
  - Output cost: `(output_tokens / 1_000_000) * pricing["output"]`
  - Total: input + output
- **Logging**: 
  - Logs to CSV: `implementation/costs/usage.csv`
  - Columns: Timestamp, PRD, Phase, Iteration, Agent, Model, Input Tokens, Output Tokens, Cost (USD), Purpose
  - Appends to existing file
- **Session Tracking**: 
  - Tracks runs in current session
  - Provides session summary at exit
  - `finalize_cost_report()` called on exit

## Infrastructure
- **CSV Storage**: `implementation/costs/usage.csv` file.
- **Pricing Data**: Hardcoded pricing dictionary (updated manually).
- **Integration**: Integrated with all agent operations via `CostLogger`.

## Architecture and Constraints
- **Token Estimation**: Simple heuristic, may not be perfectly accurate.
- **Pricing Updates**: Pricing hardcoded, requires code updates for new models/prices.
- **CSV Format**: Simple CSV, easy to import into spreadsheets.
- **Session Tracking**: In-memory tracking, persisted to CSV on exit.

## Success Criteria
- All agent operations logged
- Token estimation reasonable
- Cost calculation accurate
- CSV logging reliable
- Session reporting works
- Cost reports useful

## Acceptance Tests
1. **Token Estimation**: Test token estimation, verify reasonable accuracy
2. **Cost Calculation**: Test cost calculation with known values, verify correct
3. **Logging**: Run agent operation, verify logged to CSV
4. **Session Tracking**: Run multiple operations, verify session summary correct
5. **Cost Report**: Run `vibe cost`, verify report displayed
6. **Model Support**: Test all supported models, verify pricing correct
7. **CSV Format**: Verify CSV format correct, importable to spreadsheet