# Claude Code is quietly burning 40% of your tokens on things it doesn't need to read

Every Claude Code session, the same thing happens.

You ask Claude to fix a bug in `auth.ts`. Claude reads the file — all 400 lines of it. Then it reads it again after making an edit, to verify. Then it reads a related file. Then it reads `package.json`. By the time you've had a ten-turn conversation, Claude has ingested the same files multiple times, read the full output of every `npm install` run, and consumed hundreds of lines of grep results where only the first five mattered.

None of this is Claude's fault. It's reading everything it's given. The problem is that "everything it's given" is massive, and most of it is noise.

Here's what a typical file read looks like, token-for-token:

```
Read auth.ts (400 lines) → 1,800 tokens
```

Here's what Claude actually needed to understand that file:

```
Imports, exported types, function signatures → 210 tokens
```

That's an 88% reduction, and Claude gets the same structural information either way. The implementation details — the function bodies, the inline comments, the error handling boilerplate — are only relevant if Claude is editing *that specific function*, at *that specific moment*. The rest is noise that eats your context window and costs real money.

---

## Measuring the waste

I built a small tool to intercept every tool call Claude Code makes and compress the output before Claude sees it. After running it across real coding sessions, here's the breakdown:

- **File reads** account for 30–50% of context in a typical session
- **Build output** (npm install, test runs) generates hundreds of tokens of logs that Claude never references
- **Grep results** are often 50+ matches when Claude only acts on the top 5

In a 30-turn session, this adds up to 40–55% of total token spend being avoidable.

The compression approach is straightforward: instead of passing Claude a 400-line file, pass it the skeleton — imports, type signatures, function signatures, class outlines. Everything Claude needs to *navigate* the code. If Claude needs the body of a specific function, it can ask for it explicitly with a symbol lookup.

---

## What the numbers look like in practice

Here's `/pith status` from a real coding session earlier today:

```
Baseline (no Pith)  ████████████████████████████████  112.6k
Pith compressed     ████████████████████████████████  105.6k  (94% of baseline)
  └ saved           ██                                  7.1k  (6% removed)

Input  →  105.6k tok
Output ←   65.8k tok
Fill       53% of 200k

Actual spend   $1.30
Without Pith   $2.39
Cost saved     $1.09
```

The 6% tool compression number looks small here because this session was output-heavy (lots of writing, not just reading). The output compression (LEAN/ULTRA modes) saved 88.8k tokens on top of that. In read-heavy debugging sessions, tool compression alone runs 30–50%.

---

## The project wiki problem

There's a second problem that doesn't show up in token counts: context loss between sessions.

Claude Code compacts conversation history when the context fills. That's fine for most things — but it loses *decisions*. Why did you choose Postgres over MySQL? Why is the auth middleware structured that way? Why did you reject that refactor in December?

These decisions aren't in the code. They're not in git commits. They're in the conversation that got compacted away.

Pith maintains a persistent wiki alongside your code. After every significant decision, it offers to save a one-line record. Over time, the wiki becomes the thing you reference when you start a new session — "why does this work this way?" has an answer.

---

## How to use it

```bash
bash <(curl -s https://raw.githubusercontent.com/abhisekjha/pith/main/install.sh)
```

One command. Hooks install globally into `~/.claude/hooks/`. Every Claude Code session from that point on, compression runs automatically — no config, no commands.

If you want to go deeper: `/pith status` shows the token flow chart. `/pith ultra` pushes output compression to maximum. `/pith symbol src/auth.ts handleLogin` extracts exactly the function you need instead of reading the whole file.

The repo is at [github.com/abhisekjha/pith](https://github.com/abhisekjha/pith). MIT license.

---

*Built this because I was spending more on Claude Code than I expected and wanted to understand why. Turns out the answer was file reads.*
