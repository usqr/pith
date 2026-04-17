#!/usr/bin/env bash
set -e

CLAUDE_DIR="${HOME}/.claude"
HOOKS_DIR="${CLAUDE_DIR}/hooks/pith"
SETTINGS="${CLAUDE_DIR}/settings.json"

echo ""
echo "Uninstalling Pith..."

# Remove hooks directory
if [ -d "${HOOKS_DIR}" ]; then
  rm -rf "${HOOKS_DIR}"
  echo "  ✓ hooks removed"
fi

# Remove slash commands
for cmd in pith budget focus pith-graph; do
  f="${CLAUDE_DIR}/commands/${cmd}.md"
  if [ -f "${f}" ]; then
    rm "${f}"
    echo "  ✓ /${cmd} command removed"
  fi
done

# Patch settings.json — remove pith hooks and statusline
if [ -f "${SETTINGS}" ]; then
  # Pass the hooks dir explicitly so we only match hook entries whose command
  # actually references OUR install path. The previous filter just substring-
  # matched "pith" anywhere in the entry JSON — any unrelated user hook with
  # "pith" in its path would have been silently deleted.
  node - "${SETTINGS}" "${HOOKS_DIR}" <<'NODESCRIPT'
const fs = require('fs');
const path = require('path');
const [,, settingsPath, hooksDir] = process.argv;

let s = {};
try { s = JSON.parse(fs.readFileSync(settingsPath, 'utf8')); } catch (_) {}

// Match Pith hook entries by their command path (not by substring).
const isOurs = (entry) => {
  if (!entry || !Array.isArray(entry.hooks)) return false;
  return entry.hooks.some(h =>
    h && typeof h.command === 'string' && h.command.includes(hooksDir)
  );
};

if (s.hooks) {
  for (const event of Object.keys(s.hooks)) {
    s.hooks[event] = (s.hooks[event] || []).filter(e => !isOurs(e));
    if (s.hooks[event].length === 0) delete s.hooks[event];
  }
  if (Object.keys(s.hooks).length === 0) delete s.hooks;
}

// Same check for statusLine: only strip if it's pointing at our bundle.
if (s.statusLine
    && typeof s.statusLine.command === 'string'
    && s.statusLine.command.includes(hooksDir)) {
  delete s.statusLine;
}

fs.writeFileSync(settingsPath, JSON.stringify(s, null, 2));
console.log('  ✓ settings.json cleaned');
NODESCRIPT
fi

echo ""
echo "Pith uninstalled. Token state preserved at ~/.pith/state.json"
echo "To remove all data: rm -rf ~/.pith"
echo ""
