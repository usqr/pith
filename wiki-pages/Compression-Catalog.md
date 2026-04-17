# Compression Catalog

Every compression layer Pith applies, with before/after examples and realistic savings estimates.

---

## 1. File skeleton (PostToolUse — Read)

**What it intercepts:** any Read tool call on a code file.

**Transformation:** runs `symbols.py --list` to extract imports, type signatures, function signatures, and class outlines. Discards implementation bodies.

**Before:**
```
// auth.ts — 400 lines
import { Request, Response } from 'express';
import jwt from 'jsonwebtoken';
// ... 40 lines of imports

interface TokenPayload {
  userId: string;
  exp: number;
  iat: number;
}

export async function handleLogin(req: Request, res: Response) {
  const { email, password } = req.body;
  // 30 lines of validation logic
  // 15 lines of DB query
  // 20 lines of JWT construction
  // 10 lines of cookie setting
}
// ... 300 more lines
```
→ 1,800 tokens

**After:**
```
// auth.ts [skeleton]
import { Request, Response } from 'express';
import jwt from 'jsonwebtoken';
[+8 imports]

interface TokenPayload { userId: string; exp: number; iat: number; }

export async function handleLogin(req: Request, res: Response): Promise<void>
export async function handleLogout(req: Request, res: Response): Promise<void>
export async function refreshToken(req: Request, res: Response): Promise<void>
export function validateToken(token: string): TokenPayload | null
[4 more exports]
```
→ 210 tokens (−88%)

**Realistic saving:** 60–90% per read. Higher for large files with dense implementations.

---

## 2. Bash/build output (PostToolUse — Bash)

**What it intercepts:** Bash tool results.

**Transformation:** extracts error/warning lines, keeps last 3 lines of stdout as context, discards verbose logs.

**Before:**
```
npm install output — 200 lines of dependency resolution,
download progress bars, version conflict warnings,
audit results, peer dependency notices...
```
→ 940 tokens

**After:**
```
[3 warnings extracted]
  WARN deprecated request@2.88.2: deprecated
  WARN peer dep missing: react@^17.0.0
  WARN deprecated har-validator@5.1.5

[Summary] npm install completed. 847 packages, 0 vulnerabilities.
Last lines:
  added 847 packages in 12s
  found 0 vulnerabilities
```
→ 80 tokens (−91%)

**Realistic saving:** 70–95% for build/install runs. Lower for short commands.

---

## 3. Grep result cap (PostToolUse — Grep)

**What it intercepts:** Grep tool results.

**Transformation:** caps output at 25 matches. Appends match count if truncated.

**Before:** 150 grep matches for a common pattern → 3,000 tokens

**After:** 25 matches + `[+125 more matches — narrow the pattern]` → 500 tokens (−83%)

**Realistic saving:** proportional to match count above 25. No cost for focused searches.

---

## 4. Payload offloading (PostToolUse — any)

**What it intercepts:** any tool result that remains >300 tokens after other compression.

**Transformation:** writes full result to `~/.pith/tmp/<hash>.txt`, emits a 3-line pointer in context.

**After:**
```
[PITH OFFLOAD: large result saved]
File: ~/.pith/tmp/abc123.txt  (1,840 tokens)
Use Read("~/.pith/tmp/abc123.txt") to access if needed.
```
→ ~30 tokens

**Realistic saving:** eliminates one-off large payloads that would otherwise dominate context.

---

## 5. Symbol extraction (on demand)

**Command:** `/pith symbol <file> <name>`

**What it does:** tree-sitter AST lookup (regex fallback) for exact function/class definition. Returns 30–50 lines instead of the full file.

**Saving:** ~95% vs reading the full file for a single function.

**Speculative fetch:** automatically includes signatures of functions called within the target function. Eliminates ~60% of follow-up symbol lookups.

---

## 6. Output compression modes (UserPromptSubmit)

**Commands:** `/pith lean` / `/pith ultra` / `/pith precise`

**Transformation:** injects compression rules into Claude's context before each response.

| Mode | Rules | Estimated output reduction |
|------|-------|---------------------------|
| lean | Drop articles, short synonyms, fragments OK | ~25% |
| precise | No filler, full sentences, no hedging | ~12% |
| ultra | Abbreviate, arrows →, tables > prose | ~42% |

**Realistic saving:** estimated from response length comparison. Varies heavily by task type — code-heavy sessions save less, explanation-heavy sessions save more.

---

## 7. Auto-escalation (UserPromptSubmit)

**What it does:** automatically activates output compression as context fills, without user intervention.

```
50% fill → LEAN activated  (if mode was off)
70% fill → ULTRA activated
85% fill → dynamic token ceiling = 8% of remaining headroom
```

Ratchets up, never down within a session.

**Realistic saving:** prevents the last 30% of a session from consuming disproportionate context on verbose responses.

---

## 8. Auto-compact (UserPromptSubmit)

**What it does:** triggers `/compact` automatically when context fill reaches 70%.

**Saving:** conversation history summarized, session continues indefinitely. Without this, sessions hard-stop at context limit.

---

## 9. Cache-Lock (SessionStart)

**What it does:** hashes session-start rules. If unchanged from last session, emits 1-line summary instead of full rules block.

**Saving:** ~300 tokens per session start. Protects prompt cache from unnecessary invalidation.

---

## 10. Input focus (on demand)

**Command:** `/pith focus <file>`

**What it does:** loads only the sections of a file relevant to the current question, using keyword matching.

**Saving:** 5–20× vs loading the full file for a targeted question.
