---
allowed-tools: Bash
description: Check for or apply a new Pith release — honours PITH_REF, PITH_PIN_SHA, PITH_VERIFY_GPG
---
Check for a new Pith release, or apply one.

**Sub-command:** $ARGUMENTS  (one of `check` (default), `apply`, `list`)

The sub-command flows through a single-quoted heredoc so shell metacharacters
in user input cannot be evaluated:

```bash
SUB=$(head -n 1 <<'PITH_EOF_7f3a9c2e'
$ARGUMENTS
PITH_EOF_7f3a9c2e
)
case "${SUB:-check}" in
  check|apply|list) ;;
  *) echo "[PITH: /pith-update takes one of: check, apply, list]"; exit 0 ;;
esac
python3 "${CLAUDE_PLUGIN_ROOT}/tools/update.py" "--${SUB:-check}"
```

Show the output verbatim. For `apply`, confirm success in one line.

### Environment
- `PITH_REF` — pin to a tag/branch/commit (default: latest tag, else `main`)
- `PITH_PIN_SHA` — abort unless resolved HEAD matches this SHA
- `PITH_VERIFY_GPG=1` — require that `PITH_REF` be a signed tag
