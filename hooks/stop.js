#!/usr/bin/env node
'use strict';
// Pith — Stop hook
// Runs when Claude finishes a response.
// Updates token counter with actual usage if available, else estimates from response length.

const { loadProjectState, saveProjectState } = require('./config');

let raw = '';
process.stdin.on('data', c => { raw += c; });
process.stdin.on('end', () => {
  try {
    const data = JSON.parse(raw);
    const proj = loadProjectState();
    const updates = {};

    // Real token counts if Claude Code exposes them in stop event
    if (data.usage) {
      updates.input_tokens_actual  = (proj.input_tokens_actual  || 0) + (data.usage.input_tokens  || 0);
      updates.output_tokens_actual = (proj.output_tokens_actual || 0) + (data.usage.output_tokens || 0);
      // Prefer actual over estimate
      updates.input_tokens_est = updates.input_tokens_actual;
    } else if (data.response) {
      // Estimate output tokens, add to input_tokens_est (output becomes input next turn)
      const outEst = Math.ceil(String(data.response).length / 4);
      updates.output_tokens_est = (proj.output_tokens_est || 0) + outEst;
      updates.input_tokens_est  = (proj.input_tokens_est  || 0) + outEst;
    }

    // Accumulate lifetime total
    const sessionSaved = proj.tokens_saved_session || 0;
    updates.tokens_saved_total = (proj.tokens_saved_total || 0) + sessionSaved;

    saveProjectState(updates);
  } catch (e) { /* silent */ }
  process.exit(0);
});
