# Context Knowledge Base -- Index

> This file is a manifest of all available context chunks. The Router loads this
> file to determine which chunks to pull into a session. Context chunks are
> loaded on-demand, never all at once.
>
> **For large knowledge bases (100+ files),** use the retrieval system instead
> of scanning this index manually:
> `python -m retrieval search "your query"` or the `search_knowledge` MCP tool.
>
> **Format:** Each entry lists the chunk file, its domain scope, and a one-line
> description of what it contains.

---

## Shared Context (cross-domain)

These chunks contain frameworks and knowledge applicable across multiple domains.
Load when the domain file references them or when working across domains.

| File | Description | Load When |
|------|-------------|-----------|
| `shared/writing-style.md` | Hard rules: no semicolons, no em dashes, no AI slop, banned phrases list | ALWAYS. Referenced by AGENTS.md at Stage 4 and Stage 5. Non-negotiable. |
| `shared/mental-models.md` | First principles, systems thinking, inversion, second-order effects | Complex strategic decisions in any domain |
| `shared/communication-frameworks.md` | Pyramid Principle detail, SCQA, Minto, storytelling structures | Any deliverable requiring structured communication |

---

## Domain-Specific Context

These chunks contain deep reference material for specific domains.
Load only when working within that domain AND the depth requires it.

### Business Consulting
| File | Description | Load When |
|------|-------------|-----------|
| (to be created as needed) | Industry-specific benchmarks and data | Industry-specific engagements |

### Context Engineering
| File | Description | Load When |
|------|-------------|-----------|
| (to be created as needed) | Embedding model benchmarks, retrieval evaluation datasets | Deep retrieval system tuning |

### Course Creation
| File | Description | Load When |
|------|-------------|-----------|
| (to be created) | | |

### Business Law
| File | Description | Load When |
|------|-------------|-----------|
| (to be created) | | |

### Accounting & Tax
| File | Description | Load When |
|------|-------------|-----------|
| (to be created) | | |

### Research & Authorship
| File | Description | Load When |
|------|-------------|-----------|
| (to be created) | | |

### Go-to-Market Strategy
| File | Description | Load When |
|------|-------------|-----------|
| (to be created) | | |

---

## Context Lifecycle

1. **Creation:** Context chunks are created when a domain file needs deeper reference
   material than what fits in the domain file itself. The domain file should be
   self-sufficient for Tier 1-2 work. Context chunks enable Tier 3 depth.

2. **Loading:** The Router decides which chunks to load based on the request classification.
   For small knowledge bases, load manually from this index.
   For large knowledge bases (100+ files), use the retrieval engine:
   - CLI: `python -m retrieval context "query" --budget 2000`
   - MCP: `get_context` tool with query and max_tokens
   Rule: never load more than 3 context chunks per request.

3. **Indexing:** After creating or modifying context files, run
   `python -m retrieval index` to update the search index.

4. **Updating:** Context chunks should be updated when the information they contain
   becomes outdated. Date-stamp all data-heavy chunks.

5. **Archiving:** Move outdated chunks to `context/archive/` rather than deleting them.
