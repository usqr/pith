---
allowed-tools: Bash
description: Set a hard token ceiling per response (e.g. /budget 100) or clear it (/budget off)
---
Run the Pith budget hook and apply the token ceiling.

**Argument:** $ARGUMENTS

Step 1 — execute the hook:
```bash
echo '{"prompt":"/budget $ARGUMENTS"}' | node "${CLAUDE_PLUGIN_ROOT}/hooks/prompt-submit.js"
```

Step 2 — apply the result:
- If a token limit was set: enforce it for every response from this point forward
- If the budget was cleared: resume normal response length

Step 3 — confirm in one line.
