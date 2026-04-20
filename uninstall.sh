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

# Patch settings.json — remove pith hooks and restore any pre-Pith statusline.
if [ -f "${SETTINGS}" ]; then
  # Pass the hooks dir explicitly so we only match hook entries whose command
  # actually references OUR install path. The previous filter just substring-
  # matched "pith" anywhere in the entry JSON — any unrelated user hook with
  # "pith" in its path would have been silently deleted.
  PITH_CONFIG="${HOME}/.config/pith/config.json"
  node - "${SETTINGS}" "${HOOKS_DIR}" "${PITH_CONFIG}" <<'NODESCRIPT'
const fs = require('fs');
const path = require('path');
const [,, settingsPath, hooksDir, pithCfgPath] = process.argv;

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

// Restore the user's pre-Pith statusline if we saved one; otherwise strip
// ours entirely. Only touch statusLine if it's in fact ours.
if (s.statusLine
    && typeof s.statusLine.command === 'string'
    && s.statusLine.command.includes(hooksDir)) {
  let original = null;
  try {
    const cfg = JSON.parse(fs.readFileSync(pithCfgPath, 'utf8'));
    if (cfg && cfg.original_statusline && cfg.original_statusline.command) {
      original = cfg.original_statusline;
    }
  } catch (_) {}
  if (original) {
    s.statusLine = original;
    console.log('  ✓ original statusline restored');
  } else {
    delete s.statusLine;
  }
}

fs.writeFileSync(settingsPath, JSON.stringify(s, null, 2));
console.log('  ✓ settings.json cleaned');
NODESCRIPT
fi

echo ""
echo "Pith uninstalled. Token state preserved at ~/.pith/state.json"
echo "To remove all data: rm -rf ~/.pith"
echo ""
