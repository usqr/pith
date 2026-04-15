#!/usr/bin/env node
'use strict';
// Pith — UserPromptSubmit hook
// Parses /pith commands, tracks token estimates, injects per-message context.

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { loadConfig, loadProjectState, saveProjectState, pluginRoot } = require('./config');

const OUTPUT_MODES = new Set(['lean', 'precise', 'ultra', 'off']);
const SKILL_CMDS   = new Set(['debug', 'review', 'arch', 'plan', 'commit']); // handled by skill system

let raw = '';
process.stdin.on('data', c => { raw += c; });
process.stdin.on('end', () => {
  try {
    const data   = JSON.parse(raw);
    const prompt = (data.prompt || '').trim();
    const lower  = prompt.toLowerCase();
    const config = loadConfig();
    const proj   = loadProjectState();
    const root   = pluginRoot();
    const out    = [];

    // ── /pith <arg> ────────────────────────────────────────────────────────
    if (lower.startsWith('/pith')) {
      const parts = prompt.trim().split(/\s+/);
      const arg   = (parts[1] || '').toLowerCase();
      const rest  = parts.slice(2).join(' ');

      if (OUTPUT_MODES.has(arg)) {
        saveProjectState({ mode: arg });
        out.push(arg === 'off'
          ? 'PITH OUTPUT COMPRESSION: deactivated.'
          : modeRules(arg, root));

      } else if (arg === '' || arg === 'on') {
        const m = proj.mode && proj.mode !== 'off' ? proj.mode : (config.default_mode !== 'off' ? config.default_mode : 'lean');
        saveProjectState({ mode: m });
        out.push(modeRules(m, root));

      } else if (arg === 'wiki') {
        if (rest) {
          // /pith wiki "question" — query the wiki
          out.push(wikiQuery(rest, root));
        } else {
          // /pith wiki — toggle wiki mode
          const next = !proj.wiki_mode;
          saveProjectState({ wiki_mode: next });
          out.push(next
            ? 'PITH WIKI MODE: active. I will maintain the project wiki as we work.\n\n' + wikiModeRules(root)
            : 'PITH WIKI MODE: deactivated.');
        }

      } else if (arg === 'ingest') {
        // /pith ingest <file>
        const filePath = rest.trim();
        if (!filePath) {
          out.push('[PITH: /pith ingest requires a file path. Example: /pith ingest raw/sources/article.md]');
        } else {
          out.push(runTool('ingest.py', [filePath], root));
        }

      } else if (arg === 'lint') {
        out.push(runTool('wiki_lint.py', [], root));

      } else if (arg === 'status') {
        out.push(runTool('health.py', [], root));

      } else if (arg === 'setup') {
        // Re-run onboarding
        saveProjectState({ setup_done: false });
        out.push('PITH SETUP: resetting onboarding. On next message I will guide you through setup again.');

      } else if (arg === 'optimize-cache') {
        out.push(optimizeCache(root));

      } else if (SKILL_CMDS.has(arg)) {
        // /pith debug, /pith review, etc. — handled by Claude Code skill system
        // Just track that a skill mode was requested (no injection needed)
      }
    }

    // ── /budget <n|off> ────────────────────────────────────────────────────
    if (lower.startsWith('/budget')) {
      const parts = prompt.trim().split(/\s+/);
      const arg   = (parts[1] || '').toLowerCase();
      if (arg === 'off' || arg === '0') {
        saveProjectState({ budget: null });
        out.push('TOKEN BUDGET: cleared.');
      } else {
        const n = parseInt(arg, 10);
        if (!isNaN(n) && n > 0) {
          saveProjectState({ budget: n });
          out.push(`HARD TOKEN LIMIT: ≤${n} tokens this response. Count as you write. Stop when done. No apology for brevity.`);
        }
      }
    }

    // ── /focus <file> ──────────────────────────────────────────────────────
    if (lower.startsWith('/focus ')) {
      const filePath = prompt.slice('/focus '.length).trim();
      out.push(runTool('focus.py', [filePath, '--question', data.prompt || ''], root));
    }

    // ── Per-message: inject active budget ──────────────────────────────────
    const budget = loadProjectState().budget;
    if (budget && !lower.startsWith('/pith') && !lower.startsWith('/budget')) {
      out.push(`[TOKEN LIMIT: ≤${budget} tokens this response]`);
    }

    // ── Token estimate tracking ────────────────────────────────────────────
    const est = Math.ceil(prompt.length / 4);
    const newEst = (proj.input_tokens_est || 0) + est;
    saveProjectState({ input_tokens_est: newEst });

    // ── Auto-compact nudge at 70% context ─────────────────────────────────
    const CONTEXT_LIMIT = 200000;
    const COMPACT_THRESHOLD = 0.70;
    const usageRatio = newEst / CONTEXT_LIMIT;
    if (usageRatio >= COMPACT_THRESHOLD && !proj.compact_nudged) {
      saveProjectState({ compact_nudged: true });
      out.push(
        `[PITH: Context at ${Math.round(usageRatio * 100)}%. Run /compact now to summarize history and free space.]`
      );
    }

    // ── Mark setup done if user responded to onboarding ───────────────────
    if (!proj.setup_done && prompt.length > 0) {
      // Will be properly set by setup.py; for now just acknowledge first interaction
    }

    if (out.length) process.stdout.write(out.filter(Boolean).join('\n\n'));
  } catch (e) { /* silent */ }
  process.exit(0);
});

// ── Helpers ──────────────────────────────────────────────────────────────────

function modeRules(mode, root) {
  try {
    let content = fs.readFileSync(path.join(root, 'skills', 'pith', 'SKILL.md'), 'utf8')
      .replace(/^---[\s\S]*?---\s*/, '');
    content = content.split('\n').filter(l => {
      const m = l.match(/^\|\s*\*\*(\w+)\*\*\s*\|/);
      return !m || m[1] === mode;
    }).join('\n');
    return `PITH MODE: ${mode.toUpperCase()}\n\n${content}`;
  } catch (e) {
    const rules = { precise: 'Drop filler/hedging. Full sentences.', lean: 'Drop articles. Fragments OK.', ultra: 'Max compression. Abbreviate. Tables.' };
    return `PITH MODE: ${mode.toUpperCase()}. ${rules[mode] || rules.lean} Technical terms exact. Code unchanged. ACTIVE EVERY RESPONSE.`;
  }
}

function wikiModeRules(root) {
  try {
    return fs.readFileSync(path.join(root, 'skills', 'pith-wiki', 'SKILL.md'), 'utf8')
      .replace(/^---[\s\S]*?---\s*/, '');
  } catch (e) {
    return 'Maintain wiki pages as we work. After decisions, bugs solved, or architecture discussions, offer to save to wiki/. Keep pages concise and cross-linked.';
  }
}

function wikiQuery(question, root) {
  return runTool('wiki.py', ['--question', question], root);
}

function optimizeCache(root) {
  // Read CLAUDE.md and restructure for cache optimization
  try {
    const claudeMd = path.join(process.env.CLAUDE_CWD || process.cwd(), 'CLAUDE.md');
    if (!fs.existsSync(claudeMd)) return '[PITH: No CLAUDE.md found in current directory]';
    const content = fs.readFileSync(claudeMd, 'utf8');
    return `PITH CACHE OPTIMIZATION TASK:\n\nRead CLAUDE.md (${content.split('\n').length} lines).\n` +
      'Restructure it so stable sections (project overview, file structure, conventions) come FIRST, ' +
      'and volatile sections (current tasks, recent changes) come LAST. ' +
      'The first ~80% should never change session-to-session. ' +
      'Write the restructured version back to CLAUDE.md. ' +
      'Then confirm how many tokens are now in the stable prefix.';
  } catch (e) {
    return `[PITH: cache optimization failed — ${e.message}]`;
  }
}

function runTool(script, args, root) {
  try {
    const toolPath = path.join(root, 'tools', script);
    if (!fs.existsSync(toolPath)) return `[PITH: tool ${script} not found]`;
    const escaped = args.map(a => `"${String(a).replace(/"/g, '\\"')}"`).join(' ');
    return execSync(`python3 "${toolPath}" ${escaped}`, { timeout: 30000, encoding: 'utf8', cwd: process.env.CLAUDE_CWD || process.cwd() }).trim();
  } catch (e) {
    return `[PITH: ${script} failed — ${(e.stderr || e.message || '').slice(0, 200)}]`;
  }
}
