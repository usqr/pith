# Pith

**~50% fewer tokens in a typical Claude Code session. Zero config. Install once.**

```bash
bash <(curl -s https://raw.githubusercontent.com/abhisekjha/pith/main/install.sh)
```

---

## How it works

Pith installs four hooks into Claude Code's lifecycle. Every session, every project, automatically.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Claude Code Session                         │
│                                                                 │
│  [SessionStart] ──► Inject rules, restore mode, cache-lock      │
│                                                                 │
│  User prompt                                                    │
│       │                                                         │
│  [UserPromptSubmit] ──► Parse /pith commands, inject context    │
│       │                                                         │
│  Claude thinks + calls tools                                    │
│       │                                                         │
│  [PostToolUse] ──► Compress tool output                         │
│    • File reads   → skeleton (imports + signatures only)        │
│    • Bash output  → errors + 3-line summary                     │
│    • Grep results → capped at 25 matches                        │
│    • Large output → offloaded to ~/.pith/tmp/, 3-line pointer   │
│       │                                                         │
│  Claude responds                                                │
│       │                                                         │
│  [Stop] ──► Record token usage, accumulate lifetime stats       │
└─────────────────────────────────────────────────────────────────┘
```

The PostToolUse hook is where most savings happen — file reads alone account for 30–50% of context in a typical coding session.

---

## What gets compressed

| Layer | What happens | Typical saving |
|-------|-------------|----------------|
| File reads | skeleton only — imports, signatures, types | −88% per read |
| Bash/build output | errors + summary, discard verbose logs | −91% per run |
| Grep results | capped at 25 matches | prevents runaway searches |
| Large payloads | offloaded to `~/.pith/tmp/`, pointer left in context | prevents bloat |
| Symbol extraction | exact function/class lines via tree-sitter | ~95% vs full file |
| Output compression | lean/ultra modes, auto-escalation as context fills | 25–42% of output |
| Auto-compact | history summarized at 70% fill | unlimited sessions |
| Cache-Lock | session rules hashed — skipped if unchanged | ~300 tok/session |

In a 30-turn coding session: tool compression + auto-compact alone cuts spend by ~40–55%.

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

Or from inside Claude Code:
```
/pith install
```

One command. Hooks install globally into `~/.claude/hooks/`. Every session from that point on.

---

## Key commands

**Token status**
```
/pith status    → ASCII token flow chart — baseline vs compressed vs output
/pith report    → interactive HTML dashboard (~/.pith/report.html)
```

![/pith status — token flow chart, compression ratio, cost breakdown](assets/status-screenshot-v1.1.png)

**Output compression** (on demand or automatic)
```
/pith           → lean mode (drop filler, short synonyms)
/pith ultra     → maximum (abbreviate, arrows, tables)
/pith precise   → tight but full sentences
/pith off       → disable
```

Auto-escalation ratchets compression as context fills:
```
50% fill → LEAN activated
70% fill → ULTRA activated
85% fill → dynamic token ceiling
```

**Code navigation**
```
/pith symbol src/auth.ts handleLogin   → exact 30–50 lines (~95% vs full file)
/pith symbol --list src/auth.ts        → all symbols with line numbers
/pith focus src/services/auth.ts       → load only sections relevant to question
```

**Project wiki**
```
/pith ingest <file>                    → extract entities, claims, contradictions
/pith ingest --url <url>               → fetch URL and ingest
/pith compile                          → re-synthesize all sources into wiki pages
/pith wiki "how does auth work?"       → search with citations
/pith lint                             → contradictions, gaps, missing pages
```

**Structured formats**
```
/pith debug     problem / cause / fix / verify
/pith review    L42: BUG token expiry. Fix: token.exp * 1000
/pith arch      options table + decision + risks
/pith plan      numbered steps + risks + done-when
/pith commit    feat(auth): add token refresh on 401
```

→ Full command reference: [COMMANDS.md](COMMANDS.md)

---

## Honest numbers

These are estimates against real usage — not against "no system prompt."

```
Before Pith:  Read large-service.ts → 1,800 tokens
After Pith:   Read large-service.ts →   210 tokens   (−88%)

Before Pith:  npm install output    →   940 tokens
After Pith:   errors + summary      →    80 tokens   (−91%)
```

Session report from a real coding session:
- 105.6k input tokens (would be ~112.6k without Pith)
- 65.8k output tokens
- $1.30 actual spend vs $2.39 without
- Compression ratio: 1.1:1 tool compression + 88.8k output mode savings

---

## Project wiki

Pith maintains a persistent knowledge base alongside your code. Three workflows:

**Greenfield** — three questions on first run, wiki grows as you build.
**Brownfield** — one-session bootstrap reads the codebase and writes initial pages.
**Ongoing** — after decisions, bugs, and architecture discussions, one-line offer to save.

```
my-project/
  wiki/
    index.md        ← catalog of all pages
    log.md          ← session history
    entities/       ← tools, services, components
    concepts/       ← patterns, methods, ideas
    decisions/      ← architecture decision records
  raw/sources/      ← drop documents here, /pith ingest them
```

---

## Evals

```bash
uv run python evals/harness.py    # generate snapshot (needs ANTHROPIC_API_KEY)
python3 evals/measure.py          # analyze snapshot
```

Three arms: **baseline / terse / pith**. Honest delta is pith vs terse — how much the skill adds on top of "Answer concisely."

---

## Uninstall

```bash
/pith uninstall
```

Removes hooks from `~/.claude/settings.json`. History preserved at `~/.pith/`.

---

## License

MIT
