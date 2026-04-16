'use strict';
// Pith — config and state management
// Shared by all hooks via require('./config')

const path = require('path');
const os = require('os');
const fs = require('fs');

const PITH_DIR = path.join(os.homedir(), '.pith');
const STATE_PATH = path.join(PITH_DIR, 'state.json');

const CONFIG_PATHS = [
  process.env.PITH_CONFIG,
  path.join(os.homedir(), '.config', 'pith', 'config.json'),
  path.join(process.env.XDG_CONFIG_HOME || path.join(os.homedir(), '.config'), 'pith', 'config.json'),
].filter(Boolean);

const DEFAULTS = {
  default_mode: 'off',
  auto_compact: true,
  auto_compact_threshold: 0.70,
  tool_compress: true,
  tool_compress_threshold: 30,   // lines before compression kicks in
  offload_threshold: 300,        // tokens after compression before offloading to file
  offload_stale_turns: 5,        // turns before a result is considered stale
  budget: null,
  wiki_dir: 'wiki',
};

function loadConfig() {
  for (const p of CONFIG_PATHS) {
    try {
      if (fs.existsSync(p)) {
        return { ...DEFAULTS, ...JSON.parse(fs.readFileSync(p, 'utf8')) };
      }
    } catch (e) { /* silent */ }
  }
  return { ...DEFAULTS };
}

function loadState() {
  try {
    if (fs.existsSync(STATE_PATH)) {
      return JSON.parse(fs.readFileSync(STATE_PATH, 'utf8'));
    }
  } catch (e) { /* silent */ }
  return {};
}

function saveState(updates) {
  try {
    fs.mkdirSync(PITH_DIR, { recursive: true });
    const current = loadState();
    fs.writeFileSync(STATE_PATH, JSON.stringify({ ...current, ...updates }, null, 2));
  } catch (e) { /* silent — never block a session */ }
}

// Per-project state: keyed by a hash of the working directory
// so different projects have independent mode/wiki state
function projectKey() {
  const cwd = process.env.CLAUDE_CWD || process.cwd();
  return 'proj_' + Buffer.from(cwd).toString('base64').replace(/[^a-zA-Z0-9]/g, '').slice(0, 20);
}

function loadProjectState() {
  const state = loadState();
  return state[projectKey()] || {};
}

function saveProjectState(updates) {
  const state = loadState();
  const key = projectKey();
  state[key] = { ...(state[key] || {}), ...updates };
  saveState(state);
}

// Plugin root — where the pith directory lives
// Priority: CLAUDE_PLUGIN_ROOT env → ~/.config/pith/config.json plugin_root → __dirname/..
function pluginRoot() {
  if (process.env.CLAUDE_PLUGIN_ROOT) return process.env.CLAUDE_PLUGIN_ROOT;
  for (const p of CONFIG_PATHS) {
    try {
      if (fs.existsSync(p)) {
        const cfg = JSON.parse(fs.readFileSync(p, 'utf8'));
        if (cfg.plugin_root) return cfg.plugin_root;
      }
    } catch (e) { /* silent */ }
  }
  return path.join(__dirname, '..');
}

module.exports = {
  loadConfig,
  loadState,
  saveState,
  loadProjectState,
  saveProjectState,
  pluginRoot,
  PITH_DIR,
  STATE_PATH,
  DEFAULTS,
};
