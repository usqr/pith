#!/usr/bin/env bash
# L-7: telemetry must (a) not store verbose content by default and
# (b) scrub secret-shaped strings when verbose is enabled.

set -u
cd "$(dirname "$0")/.."

PASS=0
FAIL=0
pass() { echo "  ✓ $1"; PASS=$((PASS + 1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL + 1)); }

TDIR="$(mktemp -d)"
trap 'rm -rf "$TDIR"' EXIT
export HOME="$TDIR"
mkdir -p "$TDIR/.pith"

# Build a synthetic PostToolUse event with a secret-laden file read.
# `>30` lines to trip the compression threshold.
build_event() {
  # NOTE: these values are deliberately NOT real-vendor shapes — they must
  # still trigger the scrubSecrets regex (key=value + long hex/base64) but
  # avoid GitHub's secret scanner, which will block the push otherwise.
  python3 - <<'PY'
import json
content = (
    "DATABASE_URL=postgres://user:secret@db/app\n"
    "API_KEY=FAKE_TEST_KEY_THIS_IS_NOT_A_REAL_SECRET_1234567890\n"
    "CUSTOM_SECRET=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefgh\n"
    "Authorization: Bearer FAKE_TEST_JWT_NOT_A_REAL_TOKEN_PLACEHOLDER_0123456789abcdef\n"
    "long_hex_token=deadbeefdeadbeefdeadbeefdeadbeef\n"
    + "\n".join(f"# filler line {i}" for i in range(50)) + "\n"
)
event = {
    "tool_name": "Read",
    "tool_input": {"file_path": "app/.env"},
    "tool_response": {
        "type": "text",
        "file": {
            "filePath": "app/.env",
            "numLines": len(content.splitlines()),
            "totalLines": len(content.splitlines()),
            "startLine": 1,
            "content": content,
        },
    },
}
print(json.dumps(event))
PY
}

# ── Default mode: no raw content stored ───────────────────────────────────────
echo "L-7: default mode omits raw content"
build_event | node hooks/post-tool-use.js >/dev/null 2>&1 || true

if [ ! -s "$TDIR/.pith/telemetry.jsonl" ]; then
  fail "no telemetry entry written — cannot verify defaults"
else
  LINE="$(tail -1 "$TDIR/.pith/telemetry.jsonl")"
  echo "$LINE" | grep -q '"before_head"' \
    && fail "default mode leaked before_head: $LINE" \
    || pass "default mode has no before_head"
  echo "$LINE" | grep -q '"after_head"' \
    && fail "default mode leaked after_head" \
    || pass "default mode has no after_head"
fi

# ── Verbose mode: secrets must be redacted in before_head ─────────────────────
echo
echo "L-7: verbose mode scrubs secrets"
rm -f "$TDIR/.pith/telemetry.jsonl"

build_event | PITH_TELEMETRY_VERBOSE=1 node hooks/post-tool-use.js >/dev/null 2>&1 || true

if [ ! -s "$TDIR/.pith/telemetry.jsonl" ]; then
  fail "verbose mode produced no telemetry entry"
else
  LINE="$(tail -1 "$TDIR/.pith/telemetry.jsonl")"

  # The API_KEY line should have been matched by the key=value rule and
  # replaced with ***REDACTED***; the raw fake-key suffix must not remain.
  echo "$LINE" | grep -q 'FAKE_TEST_KEY_THIS_IS_NOT_A_REAL_SECRET' \
    && fail "API key value leaked: $LINE" \
    || pass "api_key=<value> redacted"

  echo "$LINE" | grep -q 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefgh' \
    && fail "long base64-shaped secret leaked" \
    || pass "long base64-shaped secret redacted"

  echo "$LINE" | grep -q 'FAKE_TEST_JWT_NOT_A_REAL_TOKEN_PLACEHOLDER' \
    && fail "bearer token leaked" \
    || pass "bearer token redacted"

  echo "$LINE" | grep -q 'deadbeefdeadbeefdeadbeefdeadbeef' \
    && fail "long hex leaked" \
    || pass "long-hex token redacted"

  echo "$LINE" | grep -q '"before_head"' \
    && pass "verbose mode stored before_head (scrubbed)" \
    || fail "verbose mode missing before_head"
fi

# ── File permissions: telemetry.jsonl should be mode 600 ──────────────────────
echo
echo "L-7: telemetry.jsonl stored with restrictive permissions"
if [ -f "$TDIR/.pith/telemetry.jsonl" ]; then
  PERM=$(stat -f '%A' "$TDIR/.pith/telemetry.jsonl" 2>/dev/null || stat -c '%a' "$TDIR/.pith/telemetry.jsonl" 2>/dev/null)
  if [ "$PERM" = "600" ]; then
    pass "telemetry.jsonl chmod 600"
  else
    fail "telemetry.jsonl permissions are $PERM (expected 600)"
  fi
fi

echo
echo "── Results ── passed: $PASS  failed: $FAIL"
[ "$FAIL" -eq 0 ] || exit 1
