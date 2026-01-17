## First Principle: A PRD Is a Contract, Not a Task

Every PRD in your system should answer one of these questions:

- *What do we want?*
- *What went wrong?*
- *What changed?*
- *What must never change?*

If a document doesn’t clearly fit one of those, it’s not a PRD — it’s noise.

------

## The Canonical PRD Types (Recommended)

### 1. **FEATURE PRD** (Primary)

**Purpose:**
 Define new behavior the system must implement.

**This is the default PRD.**

**Characteristics:**

- Introduces capabilities
- Has success criteria
- Is expected to result in code changes
- Is implementable

**Lifecycle:**

```
backlog → next → in_progress → done
```

**Example:**

```
PRD-021: User authentication with passkeys
```

This is what Ralph is optimized for.

------

### 2. **ISSUE PRD** (Corrective)

**Purpose:**
 Capture a failure, regression, or unmet requirement.

**Created when:**

- Tests fail repeatedly
- Implementation fails
- Compliance fails
- Bugs are discovered

**Characteristics:**

- Describes what is broken
- References evidence (logs, failures)
- Does NOT propose new features
- Must be resolvable

**Lifecycle:**

```
backlog → in_progress → done
```

**Example:**

```
ISSUE-034: Token refresh fails under concurrent requests
```

ISSUE PRDs are how Ralph learns from failure instead of looping blindly.

------

### 3. **AMENDMENT PRD** (Intent Correction)

**Purpose:**
 Modify, clarify, or correct an existing PRD’s intent.

**Created when:**

- Requirements are ambiguous
- Success criteria are contradictory
- Compliance cannot be judged fairly

**Characteristics:**

- Does not implement code directly
- Alters interpretation of another PRD
- Must explicitly reference the original PRD

**Lifecycle:**

```
backlog → approved → applied
```

**Example:**

```
AMENDMENT-007: Clarify session timeout behavior in PRD-021
```

This is how intent evolves *without lying*.

------

### 4. **CONSTRAINT PRD** (System Law)

**Purpose:**
 Declare rules that all implementations must obey.

Think of these as **constitutional law**, not features.

**Examples:**

- Security requirements
- Performance ceilings
- Privacy constraints
- Regulatory rules

**Characteristics:**

- Rarely change
- Never implemented directly
- Referenced during review and compliance
- Globally applicable

**Lifecycle:**

```
active → superseded
```

**Example:**

```
CONSTRAINT-SEC-001: No plaintext credentials at rest
```

These should be injected into compliance and review, not implementation.

------

### 5. **PROCESS PRD** (Meta-System)

**Purpose:**
 Define how Ralph itself operates.

These are self-referential but necessary.

**Examples:**

- Compliance gate behavior
- Branching strategy
- Cost limits
- Approval flows

**Characteristics:**

- Affects system behavior, not product behavior
- Implemented in tooling, not product code
- Changes infrequently

**Lifecycle:**

```
draft → active → superseded
```

**Example:**

```
PROCESS-004: PRD Compliance Gate Introduction
```

The PRD you just wrote belongs here.

------

## Optional (But Useful) Types

### 6. **EXPERIMENT PRD** (Time-boxed Exploration)

**Purpose:**
 Allow intentional uncertainty without corrupting the system.

**Characteristics:**

- Has an expiration date
- May be partially implemented
- Must conclude with a decision PRD

**Lifecycle:**

```
active → concluded
```

This prevents “forever prototypes”.

------

### 7. **DEPRECATION PRD** (Intent Removal)

**Purpose:**
 Explicitly remove behavior or guarantees.

**Why it matters:**
 Systems rot when removal is implicit.

**Example:**

```
DEPRECATION-002: Remove legacy OAuth1 support
```

------

## What You Should *Not* Have

These seem tempting but will hurt you:

- “REFACTOR PRDs” → refactoring is implementation strategy, not intent
- “TASK PRDs” → tasks are steps, not contracts
- “BUGFIX PRDs” → that’s an ISSUE PRD
- “EPIC PRDs” → epics should be folders or dependencies, not documents

------

## Minimal Viable Set (If You Want to Start Lean)

If you want the smallest coherent system:

1. FEATURE
2. ISSUE
3. AMENDMENT
4. PROCESS
5. CONSTRAINT

That’s enough to represent:

- intent
- failure
- change
- law
- governance

Anything less, and Ralph starts guessing.

------

## Why This Matters for Compliance

With these types:

- Compliance checks FEATURE PRDs
- Compliance *references* CONSTRAINT PRDs
- Compliance failures generate ISSUE or AMENDMENT PRDs
- PROCESS PRDs define how compliance behaves

This creates a **closed epistemic loop**:
 nothing appears from nowhere, nothing disappears silently.

------

## Final Thought

Most systems confuse *work* with *truth*.

Your PRD taxonomy decides whether Ralph:

- chases green lights
   or
- accumulates knowledge

The list above keeps it honest — and that’s why it scales.

If you want, next step could be:

- a PRD schema per type
- or rules for which types can depend on which others
- or how normalization should treat each class differently

---

<details>
<summary>Metadata</summary>

```yaml
id: PRIN-001
title: 'First Principle: A PRD Is a Contract, Not a Task'
type: PRINCIPLE
status: active
```

</details>

<!-- vibe-id: PRIN-001 -->
