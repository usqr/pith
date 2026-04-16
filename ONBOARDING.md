# Pith — First-Time User Guide

End-to-end walkthrough from install to fluent daily use.

---

## Step 1 — Install (2 minutes)

```bash
bash <(curl -s https://raw.githubusercontent.com/abhisekjha/pith/main/install.sh)
```

Or from source:

```bash
git clone https://github.com/abhisekjha/pith
bash pith/install.sh
```

**What just happened:**
- Four hooks wired into `~/.claude/settings.json` (SessionStart, UserPromptSubmit, PostToolUse, Stop)
- Slash commands registered: `/pith`, `/budget`, `/focus`
- Token meter added to statusline
- State directory created at `~/.pith/`

You don't need to configure anything. Everything automatic is already on.

---

## Step 2 — Open Claude Code in any project

```bash
cd my-project
claude
```

**First session, first message:** Pith introduces itself:

> Pith is active — token compression running automatically. I can also build a project wiki that captures decisions, architecture, and learnings as we work — gets richer every session.
>
> New project or existing codebase?

Answer one of two ways:

---

## Step 3A — New project flow

**You say:** "new"

Claude asks three questions, one at a time:

1. *"What does this project do? One sentence is fine."*
   → e.g. "A REST API for managing podcast subscriptions."

2. *"Tech stack? Rough is fine."*
   → e.g. "Go, PostgreSQL, deployed on Fly.io."

3. *"Just you, or a team?"*
   → e.g. "Just me for now."

Claude creates your wiki scaffold:

```
my-project/
  wiki/
    index.md        ← catalog of all pages
    log.md          ← session history
    overview.md     ← project summary
    entities/       ← services, tools, components
    concepts/       ← patterns, decisions
    decisions/      ← architecture decision records
```

> Wiki ready. I'll maintain it as we build — decisions, architecture, key entities. Every session it gets richer.

---

## Step 3B — Existing codebase flow

**You say:** "existing"

Claude asks three questions:

1. *"What does it do? One sentence."*
2. *"What's the main pain — losing context between sessions, onboarding, documenting decisions?"*
3. *"Want me to bootstrap the wiki from the existing code?"*

**If yes to bootstrap:**
Claude reads `src/`, your main modules, and writes initial wiki pages in real time. Watch the wiki build as it reads. One session.

**If no:** wiki starts empty, grows from today's work forward.

---

## Step 4 — See automatic compression working

Run any tool-heavy task:

```
read a large file, or run grep across the codebase
```

Watch the statusline:

```
PITH 8k/200k        ← token meter, always visible
```

Without Pith, reading a 400-line TypeScript file costs ~1,800 tokens.
With Pith, same read costs ~210 tokens. The PostToolUse hook strips it to imports, signatures, types — the skeleton Claude actually needs.

Compression fires automatically when tool output exceeds 30 lines. You never invoke it manually.

---

## Step 5 — Try output compression

Default: no output compression. Start it:

```
/pith
```

Claude switches to LEAN mode — drops articles, hedging, filler. Technical substance unchanged.

Three levels:

| Command | Effect |
|---------|--------|
| `/pith` or `/pith lean` | Drop articles/filler. Fragments OK. |
| `/pith precise` | Full sentences, no filler. Professional. |
| `/pith ultra` | Maximum. Abbreviations, arrows →, tables over prose. |
| `/pith off` | Back to default Claude output. |

Try asking a question. Notice the response is shorter without losing information.

---

## Step 6 — Try a structured format

Debugging a bug? Try:

```
/pith debug
```

Every answer now follows: **Problem / Cause / Fix / Verify** — four fields, no prose.

Other formats:

```
/pith review    → code review: L42: BUG. Fix. (one line per issue)
/pith arch      → architecture choice: options table + decision + risks
/pith plan      → task breakdown: numbered steps + risks + done-when
/pith commit    → generates a conventional commit message for staged changes
```

Each is one-shot — active for that context, not permanent (unlike lean/ultra/precise).

---

## Step 7 — Set a token budget

Want to keep responses tight?

```
/budget 100
```

Claude now counts tokens as it writes and stops at 100. Hard ceiling.

```
/budget off     ← remove the ceiling
```

---

## Step 8 — Use the wiki

**Add a source document:**

```
/pith ingest raw/sources/architecture-notes.md
```

Claude reads it, extracts entities and concepts, shows what it'll update, waits for your OK, then writes the pages.

**Query the wiki:**

```
/pith wiki "why did we choose Redis over Postgres for sessions?"
```

Claude reads `index.md`, loads relevant pages (compressed automatically), synthesizes an answer with citations.

**Ongoing during sessions:**
After every significant decision or solved bug, Claude offers one-line:

> "Worth saving this to the wiki? (auth decision)"

Say yes or no. Wiki stays current without overhead.

**Check wiki health:**

```
/pith lint
```

Reports orphan pages, stale claims, missing cross-refs.

---

## Step 9 — Focus a large file

Have a 1,500-line file and a specific question?

```
/focus src/services/auth.ts
```

Claude extracts only the sections relevant to the current question — not the whole file.

---

## Step 10 — Check token usage

```
/pith status
```

Shows:
- Context window used (visual bar)
- Output mode active
- Token savings this session (tool compression + output compression)
- Auto-compacts triggered
- Lifetime saved

---

## Daily workflow (after onboarding)

```
cd my-project
claude                          ← Pith loads automatically, wiki context restored

/pith                           ← if you want lean output

[code, debug, build]            ← tool compression runs silently

/pith debug                     ← when hitting a bug
/pith arch                      ← when making a design choice
/pith commit                    ← when ready to commit

/pith wiki "question"           ← recall past decisions
/pith status                    ← check token usage anytime
```

---

## What's automatic (zero config)

| Feature | When it fires |
|---------|--------------|
| Tool output compression | Every tool result >30 lines |
| Token meter in statusline | Always |
| Auto-compact at 70% context | When context fills up |
| First-run onboarding | First session in a new project |
| Wiki mode persistence | Restored each session if enabled |

---

## Full command reference

| Command | What it does |
|---------|-------------|
| `/pith` | Enable lean output compression |
| `/pith precise\|lean\|ultra` | Set compression level |
| `/pith off` | Disable output compression |
| `/pith debug` | Debug format: problem/cause/fix/verify |
| `/pith review` | Review format: one line per issue |
| `/pith arch` | Arch format: options table + decision |
| `/pith plan` | Plan format: steps + risks + done-when |
| `/pith commit` | Commit message: type(scope): subject |
| `/pith wiki` | Toggle wiki mode |
| `/pith wiki "q"` | Query the project wiki |
| `/pith ingest <file>` | Add source to wiki |
| `/pith lint` | Wiki health check |
| `/pith status` | Token usage breakdown |
| `/pith setup` | Re-run onboarding |
| `/budget <n>` | Hard token ceiling per response |
| `/budget off` | Remove token ceiling |
| `/focus <file>` | Extract relevant sections from file |

---

## Uninstall

```bash
bash pith/uninstall.sh
```

Removes hooks and statusline from `~/.claude/settings.json`. Token history at `~/.pith/` preserved.

---

## What to expect

**First session:** onboarding + wiki setup (~2 min)
**Every session after:** Pith loads silently, wiki context available, compression running

Token savings in a typical 30-turn coding session: **40–55%** from tool compression + auto-compact alone. Add output compression: **55–70%**.
