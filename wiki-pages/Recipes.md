# Recipes

Common workflows with Pith — not command references, but narratives showing how the pieces fit.

---

## Debugging a bug you can't find

You have a bug. You don't know which file it's in yet.

```
/pith ultra
```

Switch to ultra first — debugging sessions get long fast, and you want output tight from the start.

Now navigate with symbols instead of full file reads:

```
/pith symbol --list src/auth/         (if it's a directory, use the specific file)
/pith symbol src/auth/middleware.ts validateToken
```

This gives you the exact function body — 30 lines instead of 400. If Claude needs to see a caller:

```
/pith symbol src/routes/api.ts authMiddleware
```

When you find the bug and fix it:

```
/pith debug
```

This forces Claude's diagnosis into `Problem / Cause / Fix / Verify` format — tight, no prose padding.

After fixing:

```
/pith commit
```

Gets you a Conventional Commits message based on what changed.

---

## Starting a new project

First session in a new directory, Pith runs onboarding automatically. Answer three questions and you get:

```
wiki/
  index.md
  overview.md
  log.md
```

Then as you build, after any significant decision, Pith offers:

```
Worth saving this as a decision record? [y/n]
```

Say yes. Takes 2 seconds. Three months later when you're wondering "why did we use Redis instead of Postgres for sessions," the answer is in `wiki/decisions/`.

---

## Picking up an existing codebase

New project you didn't write, or returning after a long break.

```
/pith wiki
```

Activates wiki mode. If there's an existing wiki, it's loaded into context at the start of each prompt.

If there's no wiki yet:

```
/pith setup
```

Runs the brownfield bootstrap: reads main files (compressed automatically), writes initial entity and concept pages. Takes one session.

Then:

```
/pith wiki "how does authentication work?"
/pith wiki "what database are we using and why?"
```

These search the wiki first, then the codebase if needed.

---

## Ingesting a spec or research paper

You have an external document — a design spec, a paper, a competitor's docs — that's relevant to current work.

```
/pith ingest raw/sources/auth-spec.pdf
# or fetch directly:
/pith ingest --url https://company.notion.site/auth-design-v2
```

Pith extracts entities, key claims, and contradictions with existing wiki pages. Shows you what it found before writing anything. Confirm → pages created.

After ingesting several sources:

```
/pith compile
```

Re-reads all sources together, identifies cross-cutting themes, creates synthesis pages with multi-source citations. Use `--dry-run` first to see the plan.

---

## Long session management

You're 50+ turns into a session and the context is getting full.

Check status:
```
/pith status
```

If fill is >60%, Pith's hindsight analysis runs automatically. It shows stale reads (files read multiple times — only the latest matters) and large early outputs now irrelevant.

```
/compact
```

Summarizes history. Session continues. Wiki and mode settings preserved.

If you're hitting quality degradation before context fills:
```
/pith budget 150
```

Hard ceiling per response — forces Claude to be concise.

---

## Code review session

You want tight, structured feedback on a PR.

```
/pith review
```

Every response is one line per issue: `L42: BUG token expiry wrong unit`. No prose, no summaries. Just the list.

For architecture questions:
```
/pith arch
```

Outputs an options table + chosen approach + risks. Good for async decisions you want to document.

After the review, save the significant decisions:
```
/pith wiki
```

Offer will appear after any decision-level discussion.

---

## Checking wiki health

After several ingests or a long project:

```
/pith lint --quick   → structural checks only (fast, no LLM)
/pith lint           → full semantic check: contradictions, gaps, missing pages, imputable facts
/pith lint --fix     → same + auto-create stubs for missing entity pages
```

Lint report is a numbered list with recommended action per issue. Contradictions show which pages conflict and what they say. Gaps show topics referenced in multiple pages but lacking their own page.
