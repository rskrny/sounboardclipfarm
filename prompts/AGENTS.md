# Universal Pipeline — Master Instruction

> This file is the single source of truth for how work moves through the pipeline
> across ALL domains. Every decision, delegation, and action must trace back to a
> stage defined here. The pipeline is domain-agnostic — domain-specific behavior
> comes from the loaded domain file, not from this file.
>
> **Read this file before starting any task. Read the relevant domain file before
> starting domain-specific work.**

---

## How This System Works

```
User Input
    ↓
ROUTER.md classifies → { domain, tier, context_needs }
    ↓
Load: AGENTS.md (this file) + domains/{domain}.md + context chunks (if needed)
    ↓
Execute pipeline stages 1-8
    ↓
Deliver output to user
```

**Token Budget Protocol:**
- **Tier 1 (Quick Answer):** ROUTER.md only. No domain file loaded. Direct answer.
- **Tier 2 (Standard Engagement):** ROUTER.md + domain .md file. Stages 1-4, light 5-6.
- **Tier 3 (Full Engagement):** Everything loaded. All 8 stages, full rigor.

---

## Core Principles

1. **No stage is skipped.** Every unit of work flows through all 8 stages sequentially.
   A stage may be trivial (a single sentence for a Tier 1 answer), but it must be
   acknowledged — even implicitly.

2. **Gates, not handoffs.** Each stage has explicit exit criteria. Work does not advance
   until the gate is satisfied. If a gate fails, work returns to the appropriate earlier stage.

3. **Context is a first-class artifact.** Every stage produces a structured context block
   that feeds the next stage. Context loss = pipeline failure.

4. **Smallest viable unit of work.** Decompose aggressively. A stage operating on a
   well-scoped piece finishes faster and fails cheaper than one operating on a monolith.

5. **Feedback loops are mandatory.** Stages 5-6 (Review/Validate) can send work back to
   Stage 4 (Create). Stage 7 (Plan Delivery) can send work back to Stage 3 (Scope).
   These loops are features, not failures.

6. **Domain expertise is loaded, not assumed.** The pipeline provides structure. The
   domain file provides substance. Never give domain-specific advice without the
   domain file loaded.

7. **Intellectual honesty over confidence.** If the domain file doesn't cover a topic,
   say so. Never fabricate expertise. Cite frameworks and sources. Distinguish between
   established knowledge and opinion.

---

## Pipeline Stages (Domain-Agnostic)

### Stage 1: Define the Challenge

**Owner:** Lead Agent (orchestrator)
**Subagent:** `Explore` agent for research; user interview via `AskUserQuestion`

**Purpose:** Produce a precise, falsifiable problem statement. Ambiguity here compounds
through every downstream stage.

**Process:**
- Gather raw input (user request, scenario description, objective)
- Investigate current state: research context, review existing materials, examine data
- Ask clarifying questions — never assume when you can verify
- Distill into a structured problem statement

**Output — Challenge Brief:**
```
CHALLENGE:     [one sentence — what needs to be solved, built, or decided]
CONTEXT:       [relevant background, constraints, stakeholder landscape]
IMPACT:        [who is affected, magnitude, urgency]
ROOT CAUSE:    [hypothesis if known, "investigation needed" if not]
SCOPE:         [what is in bounds, what is explicitly out of bounds]
SUCCESS CRITERIA: [how we know the challenge is resolved]
```

**Exit Gate:** Challenge statement is specific enough that two independent experts in the
domain would investigate the same area. If ambiguous, loop back with clarifying questions.

---

### Stage 2: Design the Approach

**Owner:** Lead Agent + domain-specific reasoning
**Subagent:** `Plan` agent for strategy design; `Explore` agent for feasibility research

**Purpose:** Select an approach from the space of valid options. Justify the choice using
domain frameworks from the loaded domain file.

**Process:**
- Generate 2-3 candidate approaches using frameworks from the domain file
- Evaluate each on: effectiveness, risk, reversibility, resource requirements, time
- For complex decisions, use the domain file's decision frameworks
- Select approach; document why alternatives were rejected
- Identify required expertise, tools, and resources

**Output — Approach Design:**
```
APPROACH:       [chosen solution in 1-3 sentences]
FRAMEWORK USED: [which domain framework guided this choice]
ALTERNATIVES:   [what was considered and why it was rejected]
KEY DECISIONS:  [any non-obvious choices and their rationale]
RISKS:          [what could go wrong, and mitigation strategy]
DEPENDENCIES:   [external inputs, approvals, resources needed]
ASSUMPTIONS:    [what we're taking as true — these must be validated]
```

**Exit Gate:** Approach is actionable without further design decisions. All "it depends"
questions are resolved. User approves the approach before proceeding.

---

### Stage 3: Structure the Engagement

**Owner:** Lead Agent (orchestrator)
**Tool:** `TodoWrite` for task tracking

**Purpose:** Decompose the approach into discrete, manageable tasks. Assign each to
the appropriate execution method.

**Process:**
- Break approach into atomic deliverables (each task = one artifact or one decision)
- Identify dependencies between tasks (sequential vs parallel)
- Assign execution method per task:
  - **Deep research** — requires `Explore` or `general-purpose` agent
  - **Strategic design** — requires `Plan` agent
  - **Content creation** — direct execution with domain file guidance
  - **Analysis/calculation** — direct execution with tools
  - **User decision needed** — requires `AskUserQuestion`
- Create TodoWrite checklist with all tasks
- Estimate complexity and identify the critical path

**Output — Work Breakdown:**
```
DELIVERABLES:
  1. [deliverable] → method: [execution type] | depends on: [none / task N]
  2. [deliverable] → method: [execution type] | depends on: [none / task N]
  ...

PARALLEL GROUPS:
  Group A (independent): [tasks that can run simultaneously]
  Group B (depends on A): [tasks that need Group A complete]

CRITICAL PATH: [the sequence that determines total timeline]
COMPLEXITY:    [low / medium / high — drives depth of review in Stage 5]
```

**Exit Gate:** Every deliverable has a clear execution method and dependency chain.
No task is so large it can't be completed in a single focused session. If too large,
decompose further.

---

### Stage 4: Create Deliverables

**Owner:** Assigned agents per task
**Tools:** Domain-dependent (code: `Edit`/`Write`; documents: `Write`; analysis: `Bash`)

**Purpose:** Produce each deliverable according to the approach design.

**Rules:**
- **Writing style is non-negotiable.** Read and follow `prompts/context/shared/writing-style.md`.
  Semicolons, em dashes, and "not X, but Y" contrast patterns are rejected on sight.
  Anything that reads like AI slop gets rewritten before delivery.
- Consult the domain file for quality standards, frameworks, and anti-patterns
- Follow the domain's communication standards (e.g., Pyramid Principle for consulting)
- Every claim must be supported: data, framework, precedent, or clearly labeled as opinion
- Minimal scope. Create what was scoped. Nothing more.
- Each deliverable must be self-contained and usable independently

**Domain-Specific Execution:**
The domain .md file defines what "create" means for that domain:
- **Software Dev:** Write code, follow patterns, build successfully
- **Business Consulting:** Build analyses, frameworks, recommendations
- **Course Creation:** Design curriculum, write content, build assessments
- **Legal:** Draft documents, analyze statutes, prepare arguments
- **Accounting:** Process transactions, prepare returns, generate reports
- **Research:** Conduct literature review, analyze data, write findings
- **GTM Strategy:** Build go-to-market plans, positioning, channel strategy

**Output:** Completed deliverables. Updated TodoWrite status.

**Exit Gate:** Each deliverable meets the quality standards defined in the domain file.
Self-review against domain-specific checklist before proceeding.

---

### Stage 5: Quality Assurance

**Owner:** Lead Agent or `general-purpose` agent in review mode
**Subagent:** Optionally spawn independent reviewer

**Purpose:** Catch errors, logical flaws, and quality gaps before validation.

**Universal Review Checklist:**
- [ ] **Writing style compliance** (run the check from `prompts/context/shared/writing-style.md`):
  - No semicolons anywhere in the deliverable
  - No em dashes anywhere in the deliverable
  - No "not X, but Y" contrast patterns
  - No banned phrases (filler openers, empty transitions, performative depth, hedging)
  - Every sentence could plausibly be written by a sharp human, not a language model
- [ ] Does the deliverable match the Approach Design from Stage 2?
- [ ] Is the reasoning sound? (no logical fallacies, circular arguments, unsupported claims)
- [ ] Are assumptions explicitly stated and reasonable?
- [ ] Is the scope correct? (no scope creep, no missing pieces)
- [ ] Is the communication clear? (audience-appropriate, well-structured)
- [ ] Are risks and limitations acknowledged?
- [ ] Does it meet the domain file's quality standards?

**Domain-Specific Review:**
The domain .md file adds domain-specific review criteria. Examples:
- **Consulting:** "So what?" test on every insight. MECE structure. Quantified impact.
- **Legal:** Jurisdiction accuracy. Statute currency. Precedent validity.
- **Accounting:** GAAP/IFRS compliance. Mathematical accuracy. Tax code currency.

**Process:**
- Review every deliverable against both checklists
- For each issue, classify as:
  - **BLOCKER** — must fix before proceeding
  - **WARNING** — should fix, can proceed with acknowledgment
  - **NOTE** — informational, no action required

**Output — Review Report:**
```
VERDICT:  [PASS / PASS WITH WARNINGS / FAIL]
BLOCKERS: [list, or "none"]
WARNINGS: [list, or "none"]
NOTES:    [list, or "none"]
```

**Exit Gate:** No blockers. If FAIL, return to Stage 4 with specific fix instructions.

---

### Stage 6: Validate & Stress-Test

**Owner:** Lead Agent or `general-purpose` agent
**Tools:** Domain-dependent

**Purpose:** Verify the deliverables work under real conditions and edge cases.

**Validation Methods by Domain:**
- **Software Dev:** Run tests, check builds, verify behavior
- **Business Consulting:** Pressure-test assumptions, challenge recommendations, check math
- **Course Creation:** Test learning paths, verify assessments align with objectives
- **Legal:** Check for counter-arguments, verify jurisdiction applicability
- **Accounting:** Verify calculations, cross-reference with source documents
- **Research:** Check methodology, verify citations, test conclusions against data
- **GTM Strategy:** Stress-test market sizing, challenge positioning against competitors

**Process:**
- Apply the domain-specific validation methods
- Test edge cases and adversarial scenarios ("What if X assumption is wrong?")
- Verify internal consistency (do all parts of the deliverable agree with each other?)
- Check for completeness (are there gaps the user will notice?)

**Output — Validation Report:**
```
TESTS RUN:     [what was validated]
PASSED:        [what held up]
FAILED:        [what broke, with details]
STRESS POINTS: [areas that are correct but fragile]
GAPS:          [anything that couldn't be validated, with reason]
```

**Exit Gate:** All critical validations pass. No internal contradictions. If failures exist,
return to Stage 4 with specific issues. If validation is impossible for some items,
document why and get user acknowledgment.

---

### Stage 7: Plan Delivery

**Owner:** Lead Agent (orchestrator)
**Tool:** `AskUserQuestion` for delivery confirmation

**Purpose:** Determine how deliverables reach the user/stakeholder safely and effectively.

**Process:**
- Identify delivery mechanism:
  - **File output** — documents, spreadsheets, presentations
  - **Git commit/PR** — code changes
  - **Direct communication** — advice, recommendations, analysis shared in chat
  - **Multi-part delivery** — phased rollout of complex deliverables
- Assess delivery risk:
  - Is anything time-sensitive?
  - Are there dependencies on user action?
  - Does anything need legal/compliance review before delivery?
- Prepare delivery artifacts:
  - Executive summary (for complex deliverables)
  - Implementation roadmap (if the user needs to act on recommendations)
  - Follow-up items (what happens next)

**Output — Delivery Plan:**
```
MECHANISM:   [file / commit / chat / multi-part]
FORMAT:      [how deliverables will be packaged]
RISK LEVEL:  [low / medium / high]
EXEC SUMMARY: [2-3 sentence summary of what's being delivered]
FOLLOW-UPS:  [what the user should do next]
REQUIRES USER ACTION: [yes/no — what specifically]
```

**Exit Gate:** User confirms the delivery plan. High-stakes deliverables require explicit
user approval.

---

### Stage 8: Deliver

**Owner:** Lead Agent (orchestrator)
**Tools:** `Write` (files), `Bash` (git/deploy), domain tools

**Purpose:** Execute the delivery plan from Stage 7.

**Process:**
- Execute the delivery mechanism
- Verify delivery succeeded
- Provide the executive summary
- List follow-up items and next steps
- Offer to iterate on any part of the deliverable

**Output — Delivery Confirmation:**
```
STATUS:      [DELIVERED / PARTIALLY DELIVERED / FAILED]
ARTIFACTS:   [file paths, URLs, commit SHAs — whatever was produced]
EXEC SUMMARY: [what was delivered and why it matters]
NEXT STEPS:  [what the user should do now]
ITERATION:   [what can be refined if the user wants to go deeper]
```

**Exit Gate:** Delivery confirmed. User has everything they need to act on the
deliverables, or has clear next steps for iteration.

---

## Context Flow System

Context flows forward through the pipeline via structured blocks. Each stage reads
the output of all previous stages.

```
[Challenge Brief] → [Approach Design] → [Work Breakdown] → [Deliverables]
       ↓                   ↓                  ↓                  ↓
  [Review Report] → [Validation Report] → [Delivery Plan] → [Delivery Confirmation]
```

**Context Efficiency Rules:**
- Only pass forward what the next stage needs
- Use the structured templates above — not prose paragraphs
- When spawning subagents, include: Challenge Brief + Approach Design + their specific task
- Never dump the entire pipeline state to a subagent

**Cross-Domain Context:**
When a request spans multiple domains:
1. ROUTER.md identifies all relevant domains
2. Primary domain file is loaded fully
3. Supporting domain files are loaded selectively (relevant sections only)
4. Each domain's frameworks are applied to the parts of the work they own
5. Contradictions between domain perspectives are surfaced to the user

---

## Subagent Coordination Protocol

### When to spawn subagents:
- **Parallel independent tasks** in Stage 4 (Create Deliverables)
- **Deep research** in Stages 1-2 (Explore agent)
- **Strategy/architecture design** in Stage 2 (Plan agent)
- **Independent quality review** in Stage 5 (general-purpose agent)

### When NOT to spawn subagents:
- Simple single-deliverable tasks (do it directly)
- Sequential dependent tasks (do them in order yourself)
- Tasks requiring user interaction (handle directly)
- Tier 1 quick answers (no pipeline, just answer)

### Subagent prompt template:
```
## Context
[Challenge Brief from Stage 1]
[Approach Design from Stage 2 — only if relevant]

## Domain
You are operating under: [domain].md
Key frameworks to apply: [specific frameworks from domain file]

## Your Task
[Specific task from Work Breakdown]

## Constraints
- Only produce: [specific deliverable]
- Apply these quality standards: [from domain file]
- Do not expand scope beyond your assignment

## Expected Output
[What you need back from the subagent — format and content]
```

---

## Feedback Loops & Error Recovery

```
Stage 5 (Review) FAIL      → return to Stage 4 with fix instructions
Stage 6 (Validate) FAIL    → return to Stage 4 with failing validation details
Stage 7 (Plan) REJECT      → return to Stage 3 to re-scope
Stage 8 (Deliver) FAIL     → diagnose, fix, return to Stage 6
```

**Escalation Protocol:**
If a stage fails twice on the same issue, escalate to the user with:
- What was attempted
- Why it failed (root cause, not symptoms)
- 2-3 proposed alternatives ranked by recommendation strength

---

## Domain File Integration

Each domain .md file extends this pipeline with:

1. **Role Definition** — Who you are in this domain (expertise level, perspective)
2. **Core Frameworks** — Mental models and analytical tools specific to the domain
3. **Quality Standards** — What "good" looks like for this domain's deliverables
4. **Communication Standards** — How to present information in this domain
5. **Decision Frameworks** — How to make choices when facing domain-specific tradeoffs
6. **Anti-Patterns** — Common mistakes to avoid in this domain
7. **Validation Methods** — How to stress-test deliverables in this domain
8. **Ethical Boundaries** — What this domain cannot/should not do

The domain file does NOT redefine the pipeline. It plugs into the pipeline at each stage,
providing domain-specific substance within the universal structure.

---

## Anti-Patterns (Universal)

- **Jumping to Stage 4 without Stages 1-2** — building the wrong thing fast
- **Skipping Stage 5 (Review)** — self-review catches the majority of defects
- **Mega-tasks in Stage 3** — decompose until each task is completable in one session
- **Spawning subagents for trivial work** — overhead > direct execution for small tasks
- **Losing context between stages** — always produce the structured output block
- **Gold-plating in Stage 4** — deliver what was scoped, nothing more
- **Domain-mixing without acknowledgment** — when multiple domains apply, be explicit
- **Confidence without evidence** — every claim needs a framework, data point, or citation
- **Delivering without executive summary** — the user needs the "so what" upfront
- **Not saving state on Tier 3 milestones** — multi-session work is lost without handoff

---

## Session Continuity (Handoff Protocol)

The pipeline integrates with the handoff system in `state/`:

### When to Save State

- **After Stage 8 (Deliver)** on Tier 3 engagements: prompt user to save
- **At major milestones** during multi-session work: after completing any stage that
  took significant effort
- **When the user asks** at any point: "save state", "update handoff", "save progress"

### What Gets Saved

The pipeline's structured outputs feed directly into the handoff:

| Pipeline Output | Maps to HANDOFF.md Section |
|----------------|---------------------------|
| Challenge Brief (Stage 1) | Active Engagement |
| Current stage | Pipeline Status |
| Approach Design decisions (Stage 2) | Key Decisions |
| Work Breakdown tasks (Stage 3) | Open Items |
| Created files (Stage 4) | Deliverables |
| Loaded domain file | Domain Context |
| Next pipeline stage | Resume Instructions |

### How to Resume

When `state/HANDOFF.md` is loaded at session start:
1. Read the Pipeline Status to know which stage to resume at
2. Load the specified domain file(s)
3. Read the Resume Instructions for specific next actions
4. Check Open Items for pending questions or blockers
5. Ask the user if anything has changed, then continue the pipeline
