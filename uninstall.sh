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
for cmd in pith budget focus; do
  f="${CLAUDE_DIR}/commands/${cmd}.md"
  if [ -f "${f}" ]; then
    rm "${f}"
    echo "  ✓ /pith ${cmd} command removed"
  fi
done

# Patch settings.json — remove pith hooks and statusline
if [ -f "${SETTINGS}" ]; then
  node - "${SETTINGS}" <<'NODESCRIPT'
const fs = require('fs');
const p  = process.argv[2];
let s = {};
try { s = JSON.parse(fs.readFileSync(p, 'utf8')); } catch (e) {}

// Remove pith hooks from all hook events
if (s.hooks) {
  for (const event of Object.keys(s.hooks)) {
    s.hooks[event] = (s.hooks[event] || []).filter(
      entry => !JSON.stringify(entry).includes('pith')
    );
    if (s.hooks[event].length === 0) delete s.hooks[event];
  }
  if (Object.keys(s.hooks).length === 0) delete s.hooks;
}

// Remove statusline if it's ours
if (s.statusLine && JSON.stringify(s.statusLine).includes('pith')) {
  delete s.statusLine;
}

fs.writeFileSync(p, JSON.stringify(s, null, 2));
console.log('  ✓ settings.json cleaned');
NODESCRIPT
fi

echo ""
echo "Pith uninstalled. Token state preserved at ~/.pith/state.json"
echo "To remove all data: rm -rf ~/.pith"
echo ""
