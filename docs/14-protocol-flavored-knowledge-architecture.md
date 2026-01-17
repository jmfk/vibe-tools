# Protocol-Flavored Knowledge Architecture

## The Serious Lane — Protocol-First Thinking

### Design Knowledge Base (DKB)
A living corpus of constraints, patterns, conventions, and known truths about your system.

**Inside it you’d have things like:**
- Layout rule semantics  
- Widget composition patterns  
- Export limitations  
- Performance heuristics  
- Security boundaries  
- Known failure modes  

**PRDs can reference it like:**
> See `DKB-Layout-Rules-v1.2`

---

## The Engineering-Precise Lane

### System Reference Documents (SRDs)
These feel like manuals, not orders.

**Good for:**
- Schema definitions  
- APIs  
- Runtime contracts  
- Simulation interfaces  
- Agent action protocols  

**PRDs cite them as:**
> Conform to `SRD-Widget-Schema`

---

## The Agent-Native Lane

### Operational Memory Files (OMFs)
This frames them as machine-consumable knowledge, not human prose.

**These are where you’d put:**
- Canonical examples  
- Golden layouts  
- Known-good widget trees  
- Anti-patterns  
- Prompting conventions for the Designer Agent  

**PRDs say:**
> Agent must load `OMF-Design-Patterns` on initialization

---

## The Hybrid That Tends to Win in Real Systems

Use a two-tier system:

**SRDs = Hard truth**  
Schemas, interfaces, protocols, contracts.

**DKBs = Soft truth**  
Patterns, heuristics, design philosophy, known traps, style guides.

Agents read both. Humans write both. PRDs reference both.

---

## A Naming Pattern That Stays Sane at Scale

If you want this to feel like infrastructure, not a wiki:

**SRDs**
- `SRD-01-Widget-Schema`  
- `SRD-02-Layout-IR`  
- `SRD-03-Simulation-API`  

**DKBs**
- `DKB-01-Design-Patterns`  
- `DKB-02-Responsive-Rules`  
- `DKB-03-Agent-Loop-Heuristics`  

---

## The Deeper Trick

Once these exist, your PRDs stop being “documents” and start becoming **linkers**.  
They don’t describe systems — they bind together knowledge modules into an executable plan.

That’s how you end up with something closer to a build protocol than a spec library:

```text
PRD → SRD → DKB → Code → Simulation → Agent → PRD again
