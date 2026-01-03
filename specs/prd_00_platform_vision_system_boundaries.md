# PRD-00 — Platform Vision & System Boundaries

## 1. Purpose
This PRD defines the **core vision, scope, and boundaries** of the Casting Database & Casting Project Platform. Its job is to prevent scope drift, clarify what this system *is* and *is not*, and establish first principles that all other PRDs must follow.

This document is normative. Later PRDs may not contradict it.

---

## 2. Product Vision

Build a **professional-grade casting operating system** that allows casting directors and productions to:
- Discover and manage talent (actors first)
- Run casting projects end-to-end (roles → candidates → auditions → decisions)
- Collaborate securely with clients (producers, directors)
- Handle modern casting workflows (selftapes, online auditions, ads)

The platform replaces fragmented tools (email, spreadsheets, Dropbox, calendars, Zoom links) with a **single authoritative system of record**.

The system is **not** a public marketplace. It is a **private, professional tool**.

---

## 3. Target Users

### Primary users (system designed for them)
- Casting Directors
- Casting Assistants

### Secondary users
- Producers
- Directors
- Production clients

### Tertiary users
- Actors (as candidates)
- Extras / participants / experts
- Other film workers (later phase)

Actors are **participants**, not customers.

---

## 4. Core Principles (Non‑Negotiable)

1. **Single Source of Truth**  
   Every candidate, role, event, and decision must have one authoritative record.

2. **Privacy by Default**  
   No client or external user sees anything unless explicitly shared.

3. **Global Identity, Local Control**  
   People exist globally; opinions, notes, and decisions are tenant-scoped.

4. **Workflow First, Not Social**  
   This is an operational system, not a network or community.

5. **Extensibility Over Perfection**  
   Schemas must evolve without migrations every time casting trends change.

6. **Auditability**  
   Actions affecting candidates and media must be traceable.

---

## 5. System Boundaries

### In Scope
- Talent database (actors first)
- Casting projects and roles
- Candidate funnel and evaluation
- Auditions (selftape, online, in‑person)
- Client review portals
- Ads and application intake
- Calendars and scheduling
- Media management (casting-related)
- Billing for casting companies

### Explicitly Out of Scope (v1)
- Public actor profiles / discovery marketplace
- Talent representation (agents, contracts)
- Payroll or payment processing to talent
- Rights management beyond casting consent
- Union compliance automation
- AI-based casting decisions (assistive tools only later)

---

## 6. Multi-Tenancy Philosophy

- The system is **multi-tenant by design**.
- Each tenant represents a casting company or organization.
- Tenants are isolated at the data level.
- A **global people directory** exists to avoid duplication.
- Tenant-specific opinions live in overlays.

No tenant can ever access another tenant’s private data.

---

## 7. Data Ownership & Responsibility

- Tenants own:
  - Their projects
  - Their candidate evaluations
  - Their communications
  - Their uploaded media

- The platform owns:
  - Global identity graph
  - Normalized talent metadata
  - Ingestion tooling

Actors retain moral ownership of likeness; tenants control access.

---

## 8. Trust & Legal Assumptions

The system assumes:
- GDPR compliance is mandatory
- Explicit consent for media submission
- Right-to-delete must be enforceable
- Access logs may be required by clients

Legal compliance tooling is a **platform responsibility**, not a tenant burden.

---

## 9. Success Criteria

The platform is successful when:
- Casting teams can run an entire project without email or shared folders
- Clients can review and decide without seeing internal notes
- Actors can submit materials without confusion or friction
- Casting data remains reusable across projects

---

## 10. Failure Modes (What Must Not Happen)

- Clients accidentally seeing rejected candidates
- Candidates accessing other candidates’ data
- Media links leaking publicly
- Duplicate identities proliferating unchecked
- Projects becoming data silos

---

## 11. Strategic Tradeoffs

- Correctness over convenience
- Privacy over virality
- Professional UX over consumer polish
- Explicit workflows over “magic”

---

## 12. Dependencies

This PRD has no dependencies.
All other PRDs depend on this document.

---

## 13. Next PRD

PRD-01 — Multi-Tenant Architecture & Identity

This will define:
- Tenant isolation model
- Auth boundaries
- Global vs tenant data split
- Identity resolution rules

