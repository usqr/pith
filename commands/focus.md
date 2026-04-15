---
allowed-tools: Bash
description: Load only the sections of a file relevant to the current question, reducing context noise
---
Load only the sections of a file relevant to the current question.

**File:** $ARGUMENTS

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/focus.py" "$ARGUMENTS"
```

Show the relevant sections to the user. If no sections match, show the file structure overview.
