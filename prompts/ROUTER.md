# Router — Request Classification & Routing Protocol

> This file is loaded FIRST for every user request. Its job is to classify the request
> and determine what resources to load. It must be lightweight — this is the "input layer"
> of the system. Every token spent here saves or wastes tokens downstream.
>
> **This file should never be modified to include domain-specific logic.** Domain logic
> lives in domain files. This file only routes.

---

## Classification Process

When a user request arrives, classify it along four dimensions:

### 1. Domain Identification

Match the request to one or more domain files in `prompts/domains/`.

**Domain Registry** (update as new domains are added):

| Domain | File | Trigger Patterns |
|--------|------|-----------------|
| Software Development | `software-dev.md` | code, build, debug, deploy, API, database, frontend, backend, devops, architecture |
| Business Consulting | `business-consulting.md` | strategy, operations, growth, market analysis, competitive advantage, organizational design, process improvement, business model, pricing, scaling |
| Course Creation | `course-creation.md` | curriculum, teaching, course, lesson plan, learning objectives, student engagement, online education, content delivery |
| Business Law | `business-law.md` | contract, liability, compliance, intellectual property, employment law, corporate structure, regulatory, terms of service, NDA |
| Accounting & Tax | `accounting-tax.md` | taxes, bookkeeping, financial statements, deductions, filing, GAAP, revenue recognition, payroll, 1099, W-2, depreciation |
| Research & Authorship | `research-authoring.md` | literature review, methodology, peer review, thesis, publication, citation, hypothesis, data analysis, academic writing |
| Go-to-Market Strategy | `gtm-strategy.md` | launch, positioning, messaging, channels, pricing strategy, market entry, customer acquisition, product-market fit, ICP, GTM |
| Audio Engineering | `audio-engineering.md` | wav, sample rate, bit depth, audio extraction, normalization, waveform, transcript alignment, audio processing |
| Media Sourcing | `media-sourcing.md` | movie source, scraping, downloading, streaming, archive, library, media repository, yt-dlp, ffmpeg |
| Media Rights Compliance | `media-rights-compliance.md` | usage rights, IP, copyright, license, public domain, authorized, compliance, policy, provenance |
| Context Engineering | `context-engineering.md` | RAG, retrieval, knowledge base, embeddings, chunking, BM25, semantic search, context window, token optimization, information density, vector search |

**Multi-Domain Detection:**
If a request touches 2+ domains, designate:
- **Primary domain** — the one that owns the core deliverable
- **Supporting domain(s)** — those that provide supplementary input

Example: "Help me structure a consulting engagement and draft the contract"
→ Primary: `business-consulting.md` | Supporting: `business-law.md`

**Unknown Domain:**
If no domain file exists for the request:
1. Check if the request can be partially served by an existing domain
2. If not, load `TEMPLATE.md` and offer to create a new domain file
3. For simple factual questions, answer directly without any domain file

---

### 2. Complexity Tier

Classify the request into one of three tiers:

**Tier 1 — Quick Answer** (no pipeline needed)
- Simple factual questions
- Definitions, explanations, clarifications
- "What is X?" / "How does Y work?" / "What's the difference between A and B?"
- Estimated effort: < 2 minutes
- **Resources loaded:** ROUTER.md only (maybe domain file for accuracy)
- **Pipeline:** Implicit. Answer directly with domain expertise.

**Tier 2 — Standard Engagement** (lightweight pipeline)
- Analysis of a specific situation
- Recommendations with supporting reasoning
- Document creation (single deliverable)
- "Analyze X" / "Recommend Y" / "Draft Z"
- Estimated effort: 2-20 minutes
- **Resources loaded:** ROUTER.md + domain .md file
- **Pipeline:** Stages 1-4 (explicit), Stages 5-6 (light self-review), Stages 7-8 (deliver in chat)

**Tier 3 — Full Engagement** (complete pipeline)
- Complex multi-part projects
- Strategic decisions with significant consequences
- Multi-deliverable engagements
- Research requiring deep investigation
- "Build a complete X" / "Design a strategy for Y" / "Create a comprehensive Z"
- Estimated effort: 20+ minutes
- **Resources loaded:** ROUTER.md + domain .md + relevant context chunks
- **Pipeline:** All 8 stages, full rigor, structured outputs at each gate

---

### 3. Context Needs

Determine what additional context should be loaded from `prompts/context/`:

**Retrieval-Assisted Loading (preferred for Tier 2-3):**
If the retrieval system is available (MCP server running or CLI accessible),
use it to find relevant context instead of scanning INDEX.md manually:
- Run `search_knowledge` or `get_context` with the user's query
- Use the results to decide which files to load
- This scales to thousands of knowledge chunks without token waste

**Manual Loading (fallback, always works):**

**Shared Context** (`context/shared/`):
- Load shared frameworks only if the domain file references them
- Common loads: mental-models.md, communication-frameworks.md

**Domain Context** (`context/by-domain/`):
- Load domain-specific reference material only for Tier 2-3 engagements
- Only load chunks relevant to the specific request (not all domain context)

**User Context** (memory system):
- Check memory for user preferences, prior engagements, business details
- Load relevant memories to personalize the approach

---

### 4. Execution Plan

Based on classification, produce the routing decision:

```
ROUTING DECISION:
  Domain:     [primary domain file to load]
  Supporting: [additional domain files, or "none"]
  Tier:       [1 / 2 / 3]
  Context:    [list of context files to load, or "none"]
  Pipeline:   [which stages to execute explicitly]
  Subagents:  [anticipated subagent needs, or "none"]
```

---

## Routing Rules

### Rule 1: Minimum Viable Context
Load the minimum context needed to answer well. More context ≠ better answers.
It means slower responses and wasted tokens.

### Rule 2: Upgrade, Don't Downgrade
If you're unsure between Tier 1 and Tier 2, choose Tier 2.
If you're unsure between Tier 2 and Tier 3, ask the user what depth they want.

### Rule 3: Domain Confidence Threshold
Only route to a domain file if you're confident the request belongs there.
A bad routing (loading the wrong domain file) is worse than no routing.

### Rule 4: Multi-Domain Coordination
When multiple domains are involved:
- Load the primary domain file fully
- From supporting domain files, load only the sections relevant to the request
- In Stage 4 (Create), apply each domain's frameworks to their respective parts
- In Stage 5 (Review), check for contradictions between domain perspectives

### Rule 5: New Domain Detection
If the user's request clearly requires domain expertise you don't have a file for:
- Acknowledge the gap
- Offer to create a new domain file using TEMPLATE.md
- For urgent requests, provide best-effort guidance with explicit caveats

### Rule 6: Escalation for Ambiguity
If the request is ambiguous about what the user actually wants:
- Don't guess and route to the wrong pipeline
- Ask a single clarifying question that resolves the ambiguity
- Use AskUserQuestion, not open-ended prose questions

---

## Performance Optimization

### Token Budget by Tier

| Tier | Typical Input Context | Typical Output |
|------|----------------------|----------------|
| Tier 1 | ~500 tokens (router only) | Direct answer, 100-500 tokens |
| Tier 2 | ~3,000 tokens (router + domain) | Structured deliverable, 500-3,000 tokens |
| Tier 3 | ~8,000 tokens (router + domain + context) | Multi-part deliverable, 2,000-10,000+ tokens |

### Caching Strategy
- ROUTER.md is always in context (it's small by design)
- Domain files are loaded per-request, but within a session, they persist
- Context chunks are loaded and released as needed
- Memory files are checked once at routing time, not re-read every stage

### Parallel Execution
In Tier 3 engagements, identify opportunities to parallelize:
- Independent research tasks (Stage 1-2)
- Independent deliverables (Stage 4)
- Review + validation can sometimes overlap (Stages 5-6)

---

## Domain File Creation Protocol

When a new domain is needed:

1. Load `TEMPLATE.md`
2. Research the domain deeply:
   - Core theories and frameworks
   - Quality standards and best practices
   - Common failure modes and anti-patterns
   - Ethical and legal boundaries
3. Create the domain file following TEMPLATE.md structure
4. Add the domain to the Domain Registry table above
5. Create a domain context directory in `context/by-domain/`
6. Test the domain file with 3 representative requests (Tier 1, 2, and 3)

---

## Router Self-Test

Before routing, verify:
- [ ] Domain identification is based on request content, not user labels
- [ ] Tier classification considers actual complexity, not surface length
- [ ] Context needs are minimal, not maximal
- [ ] Multi-domain requests have a clear primary/supporting split
- [ ] Ambiguous requests trigger clarification, not guessing
