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
    let actualOut = 0;
    if (data.usage) {
      updates.input_tokens_actual  = (proj.input_tokens_actual  || 0) + (data.usage.input_tokens  || 0);
      updates.output_tokens_actual = (proj.output_tokens_actual || 0) + (data.usage.output_tokens || 0);
      actualOut = data.usage.output_tokens || 0;
      // Prefer actual over estimate
      updates.input_tokens_est = updates.input_tokens_actual;
    } else if (data.response) {
      // Estimate output tokens, add to input_tokens_est (output becomes input next turn)
      actualOut = Math.ceil(String(data.response).length / 4);
      updates.output_tokens_est = (proj.output_tokens_est || 0) + actualOut;
      updates.input_tokens_est  = (proj.input_tokens_est  || 0) + actualOut;
    }

    // ── Output savings from active compression mode ───────────────────────
    // When lean/ultra is active, Claude writes shorter responses.
    // Savings = (what output would have been without mode) - actual output.
    // Baseline estimate: actual / (1 - compression_rate)
    // Rates are conservative estimates validated against OCD/SWEzze benchmarks.
    if (actualOut > 0) {
      const mode = proj.mode || 'off';
      const rate = mode === 'ultra' ? 0.42 : mode === 'lean' ? 0.25 : mode === 'precise' ? 0.12 : 0;
      if (rate > 0) {
        const baseline  = Math.ceil(actualOut / (1 - rate));
        const outSaved  = baseline - actualOut;
        updates.output_savings_session = (proj.output_savings_session || 0) + outSaved;
      }
    }

    // Accumulate lifetime totals
    const sessionSaved = proj.tokens_saved_session || 0;
    updates.tokens_saved_total = (proj.tokens_saved_total || 0) + sessionSaved;

    // Lifetime cost saved — split by token type (input vs output rate)
    const IN_COST_PER_M  = 3.0;   // Sonnet 4.6 input
    const OUT_COST_PER_M = 15.0;  // Sonnet 4.6 output
    const outSaved       = (proj.output_savings_session || 0) + (updates.output_savings_session
                           ? (updates.output_savings_session - (proj.output_savings_session || 0)) : 0);
    const toolSaved      = Math.max(0, sessionSaved - outSaved);
    const sessionCostSaved = (toolSaved  / 1_000_000 * IN_COST_PER_M)
                           + (outSaved   / 1_000_000 * OUT_COST_PER_M);
    updates.cost_saved_total = (proj.cost_saved_total || 0) + sessionCostSaved;

    saveProjectState(updates);
  } catch (e) { /* silent */ }
  process.exit(0);
});
