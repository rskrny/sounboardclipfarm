# Multi-Domain Request Protocol

> When a request touches 2+ domains, this file defines how to coordinate
> domain expertise without loading everything or creating contradictions.

---

## Detection

A request is multi-domain when:
- The deliverable requires expertise from 2+ domain files
- The question sits at the intersection of domains (e.g., "structure my consulting firm" = consulting + business law + accounting)
- The user explicitly references multiple areas

## Coordination Protocol

### Step 1: Designate Primary and Supporting Domains

**Primary domain:** Owns the core deliverable and sets the communication standard.
**Supporting domain(s):** Provide specialized input to specific parts of the deliverable.

Example: "Help me price my consulting services"
- Primary: `business-consulting.md` (this is a strategy question)
- Supporting: `accounting-tax.md` (tax implications of pricing structure)

### Step 2: Load Selectively

- Load primary domain file fully
- From supporting domain files, load only the relevant sections
- Do NOT load entire supporting domain files — this wastes context

### Step 3: Resolve Conflicts

When domain perspectives conflict:
1. Identify the conflict explicitly
2. Explain each domain's perspective and reasoning
3. Recommend which domain should take priority for THIS specific decision
4. Let the user decide if the recommendation isn't clear-cut

### Step 4: Unified Deliverable

The output should feel like one coherent deliverable, not a Frankenstein of domain outputs.
The primary domain's communication standards apply. Supporting domain input is integrated,
not appended.

---

## Common Multi-Domain Patterns

| Request Pattern | Primary | Supporting |
|----------------|---------|------------|
| "Start a business doing X" | business-consulting | business-law, accounting-tax |
| "Launch a product" | gtm-strategy | business-consulting |
| "Create and sell a course" | course-creation | business-consulting, gtm-strategy |
| "Structure my company" | business-consulting | business-law |
| "Research and publish findings" | research-authoring | business-consulting (if commercial) |
| "Build and deploy software" | software-dev | business-consulting (if product strategy involved) |
