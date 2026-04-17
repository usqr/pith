# Architecture

Pith installs four hooks into Claude Code's session lifecycle via `~/.claude/hooks/`. Every hook is a Node.js script that reads JSON from stdin and writes to stdout.

## The four hooks

### SessionStart (`hooks/session-start.js`)

**Fires:** once per session, before the first user prompt.

**Does:**
- Reads `~/.pith/state.json` to restore mode, wiki state, and budget from last session
- Hashes session-start rules (Cache-Lock) — if unchanged from last session, emits a 1-line summary instead of the full rules block (~300 tokens saved)
- Injects the active compression mode prompt if mode is set

**Failure mode:** if the hook errors, the session starts without compression context. Pith fails silently — never blocks a session.

---

### UserPromptSubmit (`hooks/prompt-submit.js`)

**Fires:** every time the user sends a prompt.

**Does:**
- Parses `/pith` subcommands (`lean`, `ultra`, `status`, `wiki`, `ingest`, etc.)
- Injects per-message context (mode rules, wiki index if wiki mode is on, budget ceiling)
- Syncs real token counts from the session transcript JSONL at `~/.claude/projects/<slug>/<session_id>.jsonl`
- Runs auto-escalation check: if context fill > 50%, activates LEAN; > 70%, activates ULTRA

**State written:** `mode`, `budget`, `wiki_mode`, `input_tokens_est`, `output_tokens_est`

---

### PostToolUse (`hooks/post-tool-use.js`)

**Fires:** after every tool call Claude makes (Read, Bash, Grep, WebFetch, etc.).

**This is the core compression hook.** It intercepts tool results before Claude sees them.

| Tool | Transformation | Typical saving |
|------|---------------|----------------|
| Read (code file) | `symbols.py --list` → imports + signatures only | −88% |
| Read (other file) | First 80 lines + line count notice | varies |
| Bash | Extract errors/warnings + 3-line summary | −91% |
| Grep | Cap at 25 matches | prevents runaway |
| WebFetch | Strip HTML, extract text | −60–80% |
| Any (large result) | If >300 tokens after compression: offload to `~/.pith/tmp/`, emit 3-line pointer | prevents bloat |

**State written:** `tokens_saved_session`, `skeleton_savings_session`, `bash_savings_session`, `grep_savings_session`, per-layer counters.

---

### Stop (`hooks/stop.js`)

**Fires:** when Claude finishes a response.

**Does:**
- Reads `transcript_path` from the stop event
- Parses the session JSONL to get exact `output_tokens` (sum all turns) and `input_tokens` (latest turn only — each turn's input already includes full history)
- Computes output mode savings from active compression rate
- Accumulates lifetime totals in `~/.pith/state.json`

**Why latest-entry-only for input:** summing input across all turns would count every turn's conversation history N times. The latest assistant entry's `input_tokens` = current context window size.

---

## State file

`~/.pith/state.json` — one JSON object, keyed by project (base64-encoded cwd).

```json
{
  "proj_abc123": {
    "mode": "lean",
    "budget": null,
    "input_tokens_est": 105600,
    "output_tokens_est": 65800,
    "tokens_saved_session": 7100,
    "skeleton_savings_session": 2300,
    "bash_savings_session": 3000,
    "offload_savings_session": 1800,
    "output_savings_session": 88800,
    "tokens_saved_total": 1400000,
    "cost_saved_total": 4.26
  }
}
```

---

## Tool scripts (`tools/`)

Python scripts called by hooks or skills:

| Script | Purpose |
|--------|---------|
| `symbols.py` | tree-sitter AST extraction, regex fallback — imports + signatures |
| `focus.py` | load only sections of a file relevant to current question |
| `compact.py` | manual hindsight analysis |
| `wiki.py` | search wiki pages by keyword or GrepAI semantic index |
| `ingest.py` | extract entities/claims from a file or URL, write wiki pages |
| `compile.py` | batch re-synthesis from all raw/sources/ |
| `lint.py` | structural + semantic wiki health checks |
| `graph_generator.py` | force-directed wiki knowledge graph (D3.js) |
| `health.py` | render `/pith status` ASCII panel |
| `report.py` | generate HTML dashboard |
| `telemetry.py` | compression event log |
| `hindsight.py` | stale tool result detection |
