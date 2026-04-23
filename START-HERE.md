# Start Here

This folder turns any AI into a domain expert. You ask it something. It
figures out which expertise to load, pulls in the right frameworks, and
gives you senior-professional-level output.

Two domains are included: Business Consulting (McKinsey/BCG caliber strategy)
and Context Engineering (retrieval science, information architecture). You can
create more using the template.

---

## Option A: Claude Code (Recommended, 2 minutes)

This is the fastest path. Claude Code reads the system file automatically.

1. Install Claude Code from https://claude.ai/download
2. Open this folder in Claude Code
3. When prompted, run: `python scripts/setup.py`
4. Start asking questions

That is it. The system bootstraps itself. Ask it to help with business strategy,
analyze a market, build an org chart, design a knowledge system, or anything
else the domains cover. It will route your request, load the right expertise,
and execute.

**Lite setup (no ML, faster install):**
```
python scripts/setup.py --lite
```
This skips the 80MB embedding model. You get keyword search only. Still works
great for most use cases.

---

## Option B: ChatGPT or Any Other AI

1. Open `prompts/ROUTER.md` in a text editor
2. Copy the entire contents
3. Paste it as your system prompt or custom instructions
4. When the router tells you to load a domain file, open the file from
   `prompts/domains/` and paste that too
5. For complex work, also paste `prompts/AGENTS.md`

This works with ChatGPT, Gemini, Copilot, or any AI that accepts custom
instructions.

---

## Option C: Claude API or OpenAI API

```python
with open("prompts/ROUTER.md") as f:
    system = f.read()

with open("prompts/domains/business-consulting.md") as f:
    system += "\n\n" + f.read()

# Use as your system prompt in any API call
```

The retrieval CLI also works standalone:
```
python -m retrieval context "your question" --budget 2000
```
This outputs a pre-optimized context block you can inject into any API call.

---

## What You Can Do

**Ask questions.** The router classifies your request by domain and complexity.
Simple questions get instant answers. Complex projects get the full 8-stage
pipeline: define the problem, design the approach, scope the work, create
deliverables, review, validate, plan delivery, deliver.

**Save progress.** Say "save state" during any session. The AI writes a
snapshot to `state/HANDOFF.md`. Next session, say "pick up where we left off"
and it resumes with full context.

**Explore the knowledge graph.** Run `python -m retrieval viz --open` to see
an interactive visualization of the knowledge base. Click nodes to see full
chunk content. Switch to the Tokens tab to see how the knowledge is distributed.

**Add new domains.** Read `prompts/TEMPLATE.md`, create a new file in
`prompts/domains/`, register it in `prompts/ROUTER.md`, and run
`python -m retrieval index`.

---

## Requirements

- Python 3.9 or higher (for the retrieval engine)
- Any AI that reads text (Claude, ChatGPT, Gemini, etc.)

The prompt architecture works with zero dependencies. The retrieval engine
adds search, visualization, and token optimization on top.

---

## Folder Structure (What Everything Is)

```
START-HERE.md          You are reading this
CLAUDE.md              The AI reads this automatically (Claude Code)
README.md              Full technical documentation

prompts/
  ROUTER.md            Routes your request to the right domain
  AGENTS.md            The 8-stage execution pipeline
  TEMPLATE.md          Template for creating new domain experts
  domains/             One file per domain expertise area
  context/             Knowledge base the AI draws from
  workflows/           Execution protocols

retrieval/             Search engine for the knowledge base
scripts/               Setup and maintenance scripts
state/                 Session continuity (save/resume)
```
