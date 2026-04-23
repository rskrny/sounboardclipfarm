# Complexity Tiers — Execution Depth Protocol

> This file defines how much pipeline rigor to apply based on request complexity.
> The Router assigns a tier; this file defines what that tier means operationally.

---

## Tier 1: Quick Answer

**Characteristics:**
- Simple factual question or definition
- Single-domain, no ambiguity
- Answer exists in domain file or general knowledge
- No deliverable beyond the answer itself

**Pipeline execution:**
- Stage 1: Implicit (the question IS the problem statement)
- Stage 2: Implicit (the answer IS the approach)
- Stage 3: N/A
- Stage 4: Compose the answer
- Stage 5: Self-review for accuracy (1 pass, no formal report)
- Stage 6: N/A
- Stage 7-8: Deliver in chat

**Token budget:** ~500-1,000 tokens total
**Time:** < 1 minute

**Examples:**
- "What's the difference between a C-corp and an S-corp?"
- "Explain Porter's Five Forces"
- "What's a reasonable CAC for B2B SaaS?"

---

## Tier 2: Standard Engagement

**Characteristics:**
- Analysis of a specific situation
- Requires applying domain frameworks
- Produces a single deliverable
- May require some research or calculation
- Clear enough scope that decomposition is minimal

**Pipeline execution:**
- Stage 1: Brief challenge statement (3-5 sentences, may be implicit)
- Stage 2: Select approach and frameworks (brief, may not need alternatives)
- Stage 3: Simple task list (1-3 items via TodoWrite if needed)
- Stage 4: Create the deliverable with full domain quality standards
- Stage 5: Self-review against domain checklist (1 pass, no formal report)
- Stage 6: Light validation — check assumptions and logic (no full stress test)
- Stage 7: Implicit (deliver in chat or as a file)
- Stage 8: Deliver with brief executive summary

**Token budget:** ~2,000-5,000 tokens total
**Time:** 2-15 minutes

**Examples:**
- "Analyze our pricing strategy and recommend adjustments"
- "Draft a consulting proposal for a process improvement engagement"
- "Build a market sizing model for X"
- "Review this business plan and give feedback"

---

## Tier 3: Full Engagement

**Characteristics:**
- Complex, multi-part project
- Requires deep research and analysis
- Multiple deliverables
- High stakes — recommendations will drive real decisions
- May span multiple domains
- Ambiguity that needs to be resolved

**Pipeline execution:**
- Stage 1: Full Challenge Brief with all fields
- Stage 2: Full Approach Design with alternatives and justification
- Stage 3: Detailed Work Breakdown with TodoWrite, parallel groups, dependencies
- Stage 4: All deliverables created with full domain quality standards
- Stage 5: Formal Review Report with PASS/FAIL verdict
- Stage 6: Full validation suite (all applicable methods from domain file)
- Stage 7: Full Delivery Plan with format, audience adaptation, follow-up
- Stage 8: Deliver with executive summary, implementation roadmap, follow-up items

**Token budget:** ~5,000-20,000+ tokens
**Time:** 15-60+ minutes

**Subagent usage:** Likely. Independent research tasks and deliverables can be parallelized.

**Examples:**
- "Build a complete go-to-market strategy for our new product"
- "Design an organizational restructuring plan for a 500-person division"
- "Conduct due diligence on this acquisition target"
- "Create a comprehensive curriculum for a 12-week data science bootcamp"
- "Develop a 5-year strategic plan for entering the European market"

---

## Tier Escalation Rules

1. **Always start at the classified tier.** Don't over-engineer Tier 1 work.
2. **Escalate if complexity is discovered.** If a Tier 2 request reveals Tier 3
   complexity during Stage 1-2, escalate with user acknowledgment.
3. **Never de-escalate silently.** If you think a Tier 3 request can be handled as
   Tier 2, confirm with the user before reducing rigor.
4. **User can override.** If the user says "just give me a quick answer" to what
   looks like a Tier 3 question, honor that — but note what's being skipped.
