# PRD: PRD Compliance Gate for Ralph Implementation Pipeline

## Overview

This PRD proposes the introduction of a **dedicated PRD Compliance Gate** in the Ralph implementation pipeline.  
The purpose of this gate is to verify that an implementation satisfies the **explicit intent and success criteria** of its originating PRD, after the system is already mechanically correct.

This change formalizes the distinction between *working code* and *correct product intent*.

The compliance gate is **read-only**, produces **structured output**, and is **not allowed to modify PRDs or implementation artifacts directly**.

---

## Problem Statement

The current Ralph pipeline ensures:

- Code is generated
- Tests, lint, and builds pass
- An agentic review step evaluates quality

However, none of these steps guarantee that the resulting system actually fulfills the **semantic intent** of the PRD.

This creates several risks:

- Features that “work” but do not meet stated requirements
- Silent drift between PRD intent and delivered behavior
- Agents implicitly rewriting or reinterpreting requirements without traceability
- No durable artifact explaining *why* a PRD failed or was partially delivered

In short: correctness exists, but **accountability does not**.

---

## Goals

1. Ensure every completed PRD is explicitly evaluated against its own stated intent.
2. Prevent silent rewriting or erosion of requirements.
3. Turn non-compliance into actionable, traceable work.
4. Preserve PRDs as authoritative sources of truth.
5. Strengthen Ralph as a deterministic, auditable system rather than a best-effort agent loop.

---

## Non-Goals

- Automatically modifying PRDs during compliance checks
- Re-running implementation loops inside the compliance gate
- Replacing human product judgment
- Enforcing subjective or aesthetic opinions

---

## Proposed Change

### 1. Add a PRD Compliance Gate

Introduce a new pipeline step named **PRD Compliance Check**.

**Execution order:**

1. Implementation loop completes
2. Tests and lint pass
3. Agentic review passes
4. **PRD compliance check runs**
5. Promotion to `done` or failure handling

---

### 2. Compliance Gate Responsibilities

The compliance gate evaluates:

- Declared success criteria
- Capabilities listed in the PRD
- Explicit constraints and non-functional requirements
- Edge cases described in the PRD text

The gate **does not**:
- Modify code
- Modify PRDs
- Retry implementation

It performs **evaluation only**.

---

### 3. Structured Compliance Output

The compliance gate must emit a structured, machine-readable result.

Minimum required structure:

```text
<compliance>
STATUS: PASSED | FAILED | PARTIAL | AMBIGUOUS
SUMMARY:
- Bullet-point explanation of findings
MISSING_REQUIREMENTS:
- List (if any)
VIOLATED_CONSTRAINTS:
- List (if any)
UNCLEAR_REQUIREMENTS:
- List (if any)
</compliance>