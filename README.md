# Pith

**Token optimization for Claude Code. Automatic where it matters most.**

Install it. Get 40–60% token reduction with zero behavior change.
Then go further: structured formats, project wikis, token budgets.

---

## Install

```bash
bash <(curl -s https://raw.githubusercontent.com/abhisekjha/pith/main/install.sh)
```

Or from source:
```bash
git clone https://github.com/abhisekjha/pith
bash pith/install.sh
```

One command. Works in every Claude Code project from that point on.

---

## What it does

### Automatic (zero config, works from install)

**Tool output compression** — the biggest token sink nobody touches.
When Claude reads a 400-line TypeScript file, it gets the skeleton (imports, signatures, types) — not 400 lines. When bash returns 200 lines of npm output, it gets errors + summary. When grep returns 80 matches, it gets the first 25.

```
Before: Read large-service.ts → 1,800 tokens
After:  Read large-service.ts → 210 tokens   (-88%)
```

**Token meter in statusline**
```
PITH 12k/200k
PITH:LEAN 45k/200k
PITH:WIKI 89k/200k 🟡
```

**Auto-compact at 70% context**
Conversation history is summarized automatically when it fills 70% of the context window. Sessions run indefinitely. No more "context limit reached."

**First-run wiki setup**
On your first session in a new project, Pith introduces itself and offers to build a project wiki. Three questions. Two minutes. The wiki builds itself as you work.

---

### On demand (type a command)

**Output compression**
```
/pith           → lean (drop articles, fragments OK, short synonyms)
/pith precise   → professional but tight (no filler, full sentences)
/pith ultra     → maximum (abbreviate, arrows →, tables over prose)
/pith off       → back to normal
```

**Structured formats** — each answer fits a template, no prose waste
```
/pith debug     problem / cause / fix / verify
/pith review    L42: BUG token expiry wrong unit. Fix: token.exp * 1000
/pith arch      options table + decision + risks
/pith plan      numbered steps + risks + done-when
/pith commit    feat(auth): add token refresh on 401
```

**Token budget**
```
/budget 100     → Claude responds in ≤100 tokens, hard ceiling
/budget off     → remove ceiling
```

**Focus**
```
/focus src/services/auth.ts    → extract sections relevant to current question
```

**Wiki**
```
/pith wiki "why did we choose Redis?"   → search the project wiki
/pith ingest raw/sources/article.md    → add a source, update wiki pages
/pith wiki                              → toggle wiki mode on/off
/pith lint                              → check wiki health
/pith status                            → token usage this session
```

---

## The project wiki

Pith builds and maintains a persistent knowledge base for your project.
You direct. The LLM writes and maintains everything.

```
my-project/
  wiki/
    index.md          ← catalog of all pages
    log.md            ← session history
    overview.md       ← project summary
    entities/         ← tools, services, components (one page each)
    concepts/         ← patterns, methods, ideas
    decisions/        ← architecture decision records
  raw/sources/        ← drop documents here, /pith ingest them
```

**Greenfield:** three questions on first run, wiki grows as you build.
**Brownfield:** optional bootstrap — one session to read the codebase and write initial pages.
**Ongoing:** after every decision or solution, one-line offer to save it.

The wiki never gets expensive because Pith compresses every page read. As it grows, `/focus` and `/pith wiki` load only the relevant sections.

---

## Honest numbers

Token savings come from six layers. Each is independent.

| Layer | Mechanism | Realistic reduction |
|-------|-----------|-------------------|
| Tool compression | PostToolUse hook, rule-based | 30–50% of context |
| Cache optimization | Restructure CLAUDE.md stable prefix | 10–20% of cost |
| Auto-compact | Summarize history at 70% threshold | Unlimited sessions |
| Output formats | Structured templates vs prose | 20–35% of output |
| Token budget | Hard ceiling per response | User-controlled |
| Input focus | Load only relevant file sections | 5–20x on large docs |

**What these numbers mean:** in a typical 30-turn coding session, tool compression + auto-compact alone cuts total token spend by 40–55%. Add output compression and you reach 55–70%.

These are honest estimates. Not measured against "no system prompt." Against real usage.

---

## Uninstall

```bash
bash pith/uninstall.sh
```

Removes hooks and statusline from `~/.claude/settings.json`. Token history preserved at `~/.pith/`.

---

## Evals

Pith measures itself honestly.

```bash
# Generate snapshot (needs ANTHROPIC_API_KEY)
uv run python evals/harness.py

# Analyze snapshot (reads committed results.json)
python3 evals/measure.py
```

Three arms: baseline / terse / pith. Honest delta is **pith vs terse** — how much the skill adds on top of "Answer concisely." Token counts from Claude API `usage` field, not tiktoken approximation. Quality scored by Claude-as-judge on completeness, accuracy, and actionability.

```bash
# Real API benchmarks across compression modes
uv run python benchmarks/run.py [--dry-run]
```

---

## Commands reference

| Command | What it does |
|---------|-------------|
| `/pith` | Enable lean output compression |
| `/pith precise\|lean\|ultra` | Set compression level |
| `/pith off` | Disable output compression |
| `/pith debug` | Debug format: problem/cause/fix/verify |
| `/pith review` | Review format: L42: BUG. Fix. |
| `/pith arch` | Arch format: options table + decision |
| `/pith plan` | Plan format: steps + risks + done-when |
| `/pith commit` | Commit message: type(scope): subject |
| `/pith wiki` | Toggle wiki mode |
| `/pith wiki "q"` | Query the project wiki |
| `/pith ingest <file>` | Add source to wiki |
| `/pith lint` | Wiki health check |
| `/pith status` | Token usage breakdown |
| `/pith setup` | Re-run onboarding |
| `/pith optimize-cache` | Restructure CLAUDE.md for prompt caching |
| `/budget <n>` | Hard token ceiling per response |
| `/budget off` | Remove token ceiling |
| `/focus <file>` | Extract relevant sections from a file |

---

## License

MIT
