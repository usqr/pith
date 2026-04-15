#!/usr/bin/env bash
# Pith statusline — fast badge for Claude Code statusline
# Output: "PITH 12k/200k" or "PITH:LEAN 12k/200k" or "PITH:WIKI 12k/200k"
# Uses only grep+awk — no python3 overhead on every keypress

STATE="${HOME}/.pith/state.json"
[ ! -f "$STATE" ] && echo "PITH" && exit 0

# Extract current project key (base64 of cwd, first 20 chars of alphanum)
CWD_KEY=$(echo -n "$(pwd)" | base64 | tr -d '/+=\n' | cut -c1-20)
PROJ_KEY="proj_${CWD_KEY}"

# Fast JSON extraction with grep
get_field() {
  grep -o "\"$1\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "$STATE" 2>/dev/null | \
    head -1 | sed 's/.*: *"//' | tr -d '"'
}

get_num() {
  grep -o "\"$1\"[[:space:]]*:[[:space:]]*[0-9]*" "$STATE" 2>/dev/null | \
    head -1 | grep -o '[0-9]*$'
}

MODE=$(python3 -c "
import json, sys
try:
  d = json.load(open('$STATE'))
  proj = d.get('$PROJ_KEY', {})
  print(proj.get('mode', 'off'))
except: print('off')
" 2>/dev/null || echo 'off')

WIKI=$(python3 -c "
import json, sys
try:
  d = json.load(open('$STATE'))
  proj = d.get('$PROJ_KEY', {})
  print('1' if proj.get('wiki_mode') else '0')
except: print('0')
" 2>/dev/null || echo '0')

TOKENS=$(python3 -c "
import json, sys
try:
  d = json.load(open('$STATE'))
  proj = d.get('$PROJ_KEY', {})
  t = proj.get('input_tokens_est', 0)
  print(t)
except: print(0)
" 2>/dev/null || echo '0')

# Format token count
if [ "${TOKENS:-0}" -ge 1000 ] 2>/dev/null; then
  TOKENS_FMT="$(( ${TOKENS} / 1000 ))k"
else
  TOKENS_FMT="${TOKENS:-0}"
fi

# Build badge
if [ "$WIKI" = "1" ]; then
  SUFFIX=":WIKI"
elif [ "$MODE" != "off" ] && [ -n "$MODE" ]; then
  SUFFIX=":$(echo "$MODE" | tr '[:lower:]' '[:upper:]')"
else
  SUFFIX=""
fi

echo "PITH${SUFFIX} ${TOKENS_FMT}/200k"
