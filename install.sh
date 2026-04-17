#!/usr/bin/env bash
set -e

# ── Pinning knobs (supply-chain safety) ───────────────────────────────────────
# The default installer tracks `main`. Any of these env vars can harden it:
#   PITH_REF=v1.3.0            pin to a tag (or branch, or commit SHA)
#   PITH_PIN_SHA=deadbeef...    abort unless resolved HEAD matches this SHA
#   PITH_VERIFY_GPG=1           require a signed tag (only meaningful with a tag)
#   PITH_REPO_URL=<url>         override the source repo (defaults to upstream)
#
# The installer always prints the resolved ref + SHA before applying changes.
PITH_REPO_URL="${PITH_REPO_URL:-https://github.com/abhisekjha/pith.git}"
PITH_REF="${PITH_REF:-}"
PITH_PIN_SHA="${PITH_PIN_SHA:-}"
PITH_VERIFY_GPG="${PITH_VERIFY_GPG:-}"

# ── --print-sha / --dry-run ──────────────────────────────────────────────────
# Fast read-only modes for the "download, inspect, run" pattern:
#   bash install.sh --print-sha     # show what would be installed, exit 0
#   bash install.sh --dry-run       # full resolve but no writes
PITH_DRY_RUN=0
PITH_PRINT_SHA=0
for arg in "$@"; do
  case "$arg" in
    --dry-run)    PITH_DRY_RUN=1 ;;
    --print-sha)  PITH_PRINT_SHA=1 ; PITH_DRY_RUN=1 ;;
    --help|-h)
      cat <<HELP
Usage: install.sh [--dry-run] [--print-sha]

Environment:
  PITH_REF          tag / branch / commit to install (default: main)
  PITH_PIN_SHA      abort unless resolved HEAD matches this SHA
  PITH_VERIFY_GPG   require a signed tag (PITH_REF must be a tag)
  PITH_REPO_URL     source repo (default: upstream)
HELP
      exit 0 ;;
  esac
done

# ── Self-clone when piped via curl ────────────────────────────────────────────
# bash <(curl -s ...) sets BASH_SOURCE[0] to /dev/fd/<n> — there are no
# hook files there.  Detect this and clone to a stable location, then re-exec.
_src="${BASH_SOURCE[0]}"
if [[ "$_src" == /dev/fd/* ]] || [[ "$_src" == /proc/*/fd/* ]] || [[ "$_src" == "" ]]; then
  INSTALL_SRC="${HOME}/.local/share/pith"
  echo ""
  echo "Detected curl-pipe install — cloning ${PITH_REPO_URL}"
  [ -n "${PITH_REF}" ] && echo "  ref:     ${PITH_REF}"
  [ -n "${PITH_PIN_SHA}" ] && echo "  pin SHA: ${PITH_PIN_SHA}"
  echo "  into:    ${INSTALL_SRC}"
  mkdir -p "$(dirname "${INSTALL_SRC}")"

  if [ -d "${INSTALL_SRC}/.git" ]; then
    git -C "${INSTALL_SRC}" remote set-url origin "${PITH_REPO_URL}"
    git -C "${INSTALL_SRC}" fetch --quiet --tags origin
    if [ -n "${PITH_REF}" ]; then
      git -C "${INSTALL_SRC}" checkout --quiet "${PITH_REF}"
    else
      # No explicit pin: fast-forward main so repeated installs stay current.
      git -C "${INSTALL_SRC}" checkout --quiet main 2>/dev/null || true
      git -C "${INSTALL_SRC}" pull --quiet --ff-only
    fi
  else
    if [ -n "${PITH_REF}" ]; then
      git clone --depth=1 --quiet --branch "${PITH_REF}" "${PITH_REPO_URL}" "${INSTALL_SRC}"
    else
      git clone --depth=1 --quiet "${PITH_REPO_URL}" "${INSTALL_SRC}"
    fi
  fi

  # Verify pinned SHA if set.
  ACTUAL_SHA="$(git -C "${INSTALL_SRC}" rev-parse HEAD)"
  if [ -n "${PITH_PIN_SHA}" ] && [ "${ACTUAL_SHA}" != "${PITH_PIN_SHA}" ]; then
    echo ""
    echo "ERROR: resolved HEAD ${ACTUAL_SHA} does not match PITH_PIN_SHA ${PITH_PIN_SHA}"
    echo "Aborting to avoid installing an unexpected revision."
    exit 2
  fi

  # Optional GPG tag verification (only if PITH_REF looks like a tag).
  if [ "${PITH_VERIFY_GPG}" = "1" ] && [ -n "${PITH_REF}" ]; then
    if git -C "${INSTALL_SRC}" rev-parse --verify "refs/tags/${PITH_REF}" >/dev/null 2>&1; then
      if ! git -C "${INSTALL_SRC}" verify-tag "${PITH_REF}"; then
        echo "ERROR: tag ${PITH_REF} failed GPG verification."
        exit 2
      fi
      echo "  ✓ GPG tag signature verified"
    else
      echo "ERROR: PITH_VERIFY_GPG=1 set but ${PITH_REF} is not a tag."
      exit 2
    fi
  fi

  echo "  HEAD: ${ACTUAL_SHA}"
  echo ""

  if [ "${PITH_PRINT_SHA}" = "1" ]; then
    # Just echo the SHA for scripts/humans and exit.
    echo "${ACTUAL_SHA}"
    exit 0
  fi

  # Forward the dry-run flag (but not print-sha, handled above).
  if [ "${PITH_DRY_RUN}" = "1" ]; then
    exec bash "${INSTALL_SRC}/install.sh" --dry-run
  else
    exec bash "${INSTALL_SRC}/install.sh"
  fi
fi

# ── Local install (either direct, or re-exec'd from the self-clone) ──────────
# Resolve the SHA of the checkout we're about to install, for both display and
# persistence into ~/.config/pith/config.json.
INSTALL_SHA=""
INSTALL_REF="${PITH_REF:-main}"
if command -v git >/dev/null 2>&1 && [ -d "$(dirname "${BASH_SOURCE[0]}")/.git" ] \
   || git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --git-dir >/dev/null 2>&1; then
  INSTALL_SHA="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse HEAD 2>/dev/null || echo '')"
fi

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${HOME}/.claude"
HOOKS_DIR="${CLAUDE_DIR}/hooks/pith"
SETTINGS="${CLAUDE_DIR}/settings.json"

echo ""
echo "Installing Pith..."
[ -n "${INSTALL_SHA}" ]  && echo "  ref:  ${INSTALL_REF}"
[ -n "${INSTALL_SHA}" ]  && echo "  sha:  ${INSTALL_SHA}"
echo "  into: ${HOOKS_DIR}"
echo ""

if [ "${PITH_DRY_RUN:-0}" = "1" ]; then
  echo "[dry-run] no files written."
  exit 0
fi

# Create dirs with tight permissions: ~/.pith holds telemetry and may
# capture sensitive fragments if PITH_TELEMETRY_VERBOSE=1 is ever set.
mkdir -p "${HOOKS_DIR}"
mkdir -p "${HOME}/.pith"
chmod 700 "${HOME}/.pith" 2>/dev/null || true

# Copy hooks
for f in session-start.js post-tool-use.js prompt-submit.js stop.js config.js statusline.sh; do
  cp "${PLUGIN_ROOT}/hooks/${f}" "${HOOKS_DIR}/${f}"
  echo "  ✓ hooks/${f}"
done
chmod +x "${HOOKS_DIR}/statusline.sh"

# Create symlink to skills and tools so hooks can resolve paths
ln -sfn "${PLUGIN_ROOT}/skills" "${HOOKS_DIR}/../pith-skills" 2>/dev/null || true
ln -sfn "${PLUGIN_ROOT}/tools"  "${HOOKS_DIR}/../pith-tools"  2>/dev/null || true

# Patch settings.json
node - "${SETTINGS}" "${HOOKS_DIR}" <<'NODESCRIPT'
const fs = require('fs');
const path = require('path');

const settingsPath = process.argv[2];
const hooksDir     = process.argv[3];

let settings = {};
try { settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8')); } catch (e) {}

const hook = (script, timeout, msg) => ({
  type: 'command',
  command: `node "${hooksDir}/${script}"`,
  ...(timeout  ? { timeout }        : {}),
  ...(msg      ? { statusMessage: msg } : {}),
});

const hookEntry = (event, script, timeout, msg) => ({
  matcher: '',
  hooks: [hook(script, timeout, msg)],
});

settings.hooks = settings.hooks || {};

const add = (event, script, timeout, msg) => {
  const list = settings.hooks[event] = settings.hooks[event] || [];
  const exists = list.some(h => h.hooks && h.hooks[0] && h.hooks[0].command && h.hooks[0].command.includes('pith'));
  if (!exists) list.push(hookEntry(event, script, timeout, msg));
};

add('SessionStart',      'session-start.js',  10, 'Pith: initializing...');
add('UserPromptSubmit',  'prompt-submit.js',   5, null);
add('PostToolUse',       'post-tool-use.js',  10, 'Pith: compressing...');
add('Stop',              'stop.js',            5, null);

settings.statusLine = {
  type: 'command',
  command: `bash "${hooksDir}/statusline.sh"`,
};

fs.mkdirSync(path.dirname(settingsPath), { recursive: true });
fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
console.log('  ✓ settings.json patched');
NODESCRIPT

# Install slash commands into ~/.claude/commands/
COMMANDS_DIR="${CLAUDE_DIR}/commands"
mkdir -p "${COMMANDS_DIR}"

node - "${COMMANDS_DIR}" "${HOOKS_DIR}" "${PLUGIN_ROOT}" <<'CMDSCRIPT'
const fs   = require('fs');
const path = require('path');
const cmds = process.argv[2];
const hooks = process.argv[3];
const root  = process.argv[4];

// NOTE: $ARGUMENTS is Claude Code's literal template substitution — it is NOT
// shell-escaped. The only injection-safe way to forward user args into bash is
// to place them inside a single-quoted heredoc whose delimiter cannot appear
// in normal user input. The helper then reads stdin instead of argv.
const HEREDOC_TAG = 'PITH_EOF_7f3a9c2e';

const pithMd = `---
allowed-tools: Bash
---
Run the Pith hook for this subcommand and apply the result.

**Subcommand:** $ARGUMENTS

Step 1 — execute the hook. Arguments flow via a single-quoted heredoc so
shell metacharacters in user input are never evaluated:
\`\`\`bash
node "${hooks}/prompt-submit.js" --slash /pith <<'${HEREDOC_TAG}'
$ARGUMENTS
${HEREDOC_TAG}
\`\`\`

Step 2 — act on the output:
- If the output contains compression rules (LEAN / ULTRA / PRECISE): apply them immediately and confirm the mode is active
- If the output contains a token status panel: display it to the user exactly
- If the output contains wiki results or tool output: display it
- If the output is empty (e.g. \`/pith debug\`): confirm the structured format is active and show a one-line example of it

Step 3 — confirm to the user in one line what changed or was shown.
`;

const budgetMd = `---
allowed-tools: Bash
---
Run the Pith budget hook and apply the token ceiling.

**Argument:** $ARGUMENTS

Step 1 — execute the hook (arguments passed via heredoc, never via shell args):
\`\`\`bash
node "${hooks}/prompt-submit.js" --slash /budget <<'${HEREDOC_TAG}'
$ARGUMENTS
${HEREDOC_TAG}
\`\`\`

Step 2 — apply the result:
- If a token limit was set: enforce it for every response from this point forward
- If the budget was cleared: resume normal response length

Step 3 — confirm in one line.
`;

const focusMd = `---
allowed-tools: Bash
---
Load only the sections of a file relevant to the current question.

**File:** $ARGUMENTS

The file path is delivered to focus.py via a heredoc, so metacharacters in
the path cannot trigger shell evaluation:
\`\`\`bash
python3 "${root}/tools/focus.py" --stdin-path <<'${HEREDOC_TAG}'
$ARGUMENTS
${HEREDOC_TAG}
\`\`\`

Show the relevant sections to the user. If no sections match, show the file structure overview.
`;

const graphMd = `---
allowed-tools: Bash
---
Run the Pith wiki graph generator for the current project.

\`\`\`bash
python3 "${root}/tools/graph_generator.py"
\`\`\`

The script will:
1. Scan \`./wiki/\` for \`.md\` files and extract \`[[wikilinks]]\`
2. Write \`wiki-graph.html\` to the current project root
3. Automatically open it in the default browser

If \`wiki/\` does not exist or has no \`.md\` files, tell the user to build the wiki first with \`/pith wiki\`.
`;

fs.writeFileSync(path.join(cmds, 'pith.md'),       pithMd);
fs.writeFileSync(path.join(cmds, 'budget.md'),     budgetMd);
fs.writeFileSync(path.join(cmds, 'focus.md'),      focusMd);
fs.writeFileSync(path.join(cmds, 'pith-graph.md'), graphMd);
console.log('  ✓ slash commands registered (/pith, /budget, /focus, /pith-graph)');
CMDSCRIPT

# Write CLAUDE_PLUGIN_ROOT + installed ref/SHA to config so hooks know which
# version is active (for /pith status and future /pith update).
# Values are passed via argv, NOT interpolated into a JS string literal, so
# unusual characters in $HOME / $PLUGIN_ROOT can't break the script.
mkdir -p "${HOME}/.config/pith"
node - "${HOME}/.config/pith/config.json" "${PLUGIN_ROOT}" "${INSTALL_REF}" "${INSTALL_SHA}" <<'CONFSCRIPT'
const fs = require('fs');
const [,, cfgPath, pluginRoot, ref, sha] = process.argv;
let c = {};
try { c = JSON.parse(fs.readFileSync(cfgPath, 'utf8')); } catch (_) {}
c.plugin_root   = pluginRoot;
c.installed_ref = ref || null;
c.installed_sha = sha || null;
c.installed_at  = new Date().toISOString();
fs.writeFileSync(cfgPath, JSON.stringify(c, null, 2));
try { fs.chmodSync(cfgPath, 0o600); } catch (_) {}
CONFSCRIPT
echo "  ✓ plugin root recorded (ref=${INSTALL_REF:-?} sha=${INSTALL_SHA:0:12})"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pith installed successfully."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Automatic features (active now, zero config):"
echo "  • Tool output compression — large file reads, bash, grep trimmed automatically"
echo "  • Token meter in statusline — [PITH 12k/200k]"
echo "  • Auto-compact at 70% — sessions never hit context limits"
echo "  • First-run wiki setup — offered on your first session in a new project"
echo ""
echo "On-demand commands:"
echo "  /pith                → lean output compression"
echo "  /pith precise|ultra  → adjust compression level"
echo "  /pith debug          → structured debug format"
echo "  /pith review         → structured code review"
echo "  /pith arch           → architecture decision table"
echo "  /pith plan           → task breakdown format"
echo "  /pith commit         → conventional commit message"
echo "  /pith wiki           → toggle wiki mode"
echo "  /pith status         → token usage this session"
echo "  /budget 150          → hard token ceiling"
echo "  /focus <file>        → extract relevant sections"
echo ""
echo "Start Claude Code in any project to begin."
echo ""
