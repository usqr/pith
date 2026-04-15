---
allowed-tools: Bash
description: Control Pith token compression modes and access structured output formats, wiki, and status
---
Run the Pith hook for this subcommand and apply the result.

**Subcommand:** $ARGUMENTS

Step 1 — execute the hook:
```bash
echo '{"prompt":"/pith $ARGUMENTS"}' | node "${CLAUDE_PLUGIN_ROOT}/hooks/prompt-submit.js"
```

Step 2 — act on the output:
- If the output contains compression rules (LEAN / ULTRA / PRECISE): apply them immediately and confirm the mode is active
- If the output contains a token status panel: display it to the user exactly
- If the output contains wiki results or tool output: display it
- If the output is empty (e.g. `/pith debug`): confirm the structured format is active and show a one-line example of it

Step 3 — confirm to the user in one line what changed or was shown.
