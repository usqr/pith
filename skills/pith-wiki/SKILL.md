---
name: pith-wiki
description: >
  Wiki mode — persistent knowledge base maintenance. Active during /pith wiki mode.
  Defines page formats, ingest workflow, query workflow, and lint checks.
---

## Wiki mode behavior

When wiki mode is active:
- After significant decisions: offer to save to wiki
- After bugs solved: offer to save resolution
- After architecture discussions: offer to save as decision record
- After ingest: show what was updated, ask for confirmation
- Keep all offers brief: one line. User says yes/no.

---

## Page formats

### Entity page (person, company, tool, service, component)
```markdown
# [Entity Name]

**Type:** person | org | tool | service | component
**Summary:** [2 sentences max]

## Key Facts
- [fact]
- [fact]

## Connections
- [[related-entity]] — [how they relate]

## Sources
- [source title](../raw/sources/file.md) — [date]

## Contradictions
- [claim in source A] vs [claim in source B] — unresolved
```

### Concept page (idea, pattern, method, principle)
```markdown
# [Concept Name]

**Definition:** [one sentence]
**Why it matters:** [one sentence]

## How it works
[2-4 sentences max]

## Related
- [[concept]] — [relation]

## Examples
- [concrete example]

## Open questions
- [what's still unclear]

## Sources
- [source](../raw/sources/file.md)
```

### Decision record
```markdown
# Decision: [what was decided]

**Date:** YYYY-MM-DD
**Status:** decided | revisiting | superseded

## Context
[1-2 sentences: why this decision was needed]

## Options considered
| Option | Pro | Con |
|--------|-----|-----|
| A | ... | ... |

## Decision
[what was chosen and single-sentence why]

## Consequences
- [what this enables]
- [what this constrains]
```

### Synthesis / analysis page
```markdown
# [Title]

**Thesis:** [one-sentence claim]
**Confidence:** high | medium | low

## Evidence
- [point] — [source](../raw/sources/file.md)

## Counter-evidence
- [point that argues against the thesis]

## Open questions
- [what would change this conclusion]
```

---

## index.md format

One entry per wiki page. Updated on every ingest or new page.

```markdown
# Wiki Index

## Entities
- [[EntityName]] — [one-line description] — [source count] sources

## Concepts
- [[ConceptName]] — [one-line description]

## Decisions
- [[Decision-title]] — [date] — [status]

## Syntheses
- [[Synthesis-title]] — [one-line thesis]

## Sources processed
- [Source Title](raw/sources/file.md) — [date ingested] — [pages updated]
```

---

## log.md format

Append-only. One entry per operation.

```markdown
## [YYYY-MM-DD] ingest | [Source Title]
Pages updated: [[page1]], [[page2]], [[page3]]
New pages: [[new-page]]
Contradictions found: [yes/no — detail if yes]

## [YYYY-MM-DD] query | [question summary]
Pages consulted: [[page1]], [[page2]]
Answer filed: [[synthesis-page]] (yes/no)

## [YYYY-MM-DD] lint
Issues found: [N orphan pages, M stale claims, K missing cross-refs]
```

---

## Ingest workflow

When `/pith ingest <file>` is called:

1. Read the source file
2. Extract: key entities, key claims, contradictions with existing wiki content, gaps filled
3. Show summary: "Found: 3 entities, 2 new concepts, 1 contradiction. Will update: [[page1]], [[page2]]. Create: [[new-page]]."
4. Wait for user confirmation
5. Write/update pages, update index.md, append to log.md

---

## Lint checks

When `/pith lint` is called, check for:
- Orphan pages (no inbound links from index.md or other pages)
- Pages with no sources
- Claims that contradict each other across pages (flag for review)
- Entities mentioned in source summaries but lacking their own page
- index.md entries pointing to non-existent files
- log.md entries older than 30 days with "unresolved" contradictions

Report as a numbered list with recommended action per issue.

---

## Query workflow

When `/pith wiki "<question>"`:
1. Read index.md — identify relevant page entries
2. Load those pages (Pith compresses each read automatically)
3. Synthesize answer with citations: "Based on [[page1]] and [[page2]]..."
4. Offer to file the answer: "Worth saving this as a synthesis page?"

---

## Boundaries

Never modify files in `raw/sources/` — those are immutable source documents.
Always write compressed, cross-linked pages. No verbose prose.
Every new entity or concept gets its own page — no inline-only mentions.
