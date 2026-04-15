#!/usr/bin/env python3
"""
Pith Health — token usage breakdown for the current session.
Called by /pith status.
"""
from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path

STATE   = Path.home() / '.pith' / 'state.json'
CWD_KEY = 'proj_' + re.sub(r'[^a-zA-Z0-9]', '', __import__('base64').b64encode(
    os.getcwd().encode()).decode())[:20]


def load() -> dict:
    try:
        if STATE.exists():
            d = json.loads(STATE.read_text())
            return d.get(CWD_KEY, {})
    except Exception:
        pass
    return {}


def bar(frac: float, w: int = 20) -> str:
    filled = min(round(frac * w), w)
    b = '▓' * filled + '░' * (w - filled)
    if frac > 0.85: return b + ' 🔴'
    if frac > 0.70: return b + ' 🟡'
    return b


def fmt(n: int) -> str:
    if n >= 1_000_000: return f'{n/1_000_000:.1f}M'
    if n >= 1_000:     return f'{n/1_000:.1f}k'
    return str(n)


def main():
    s = load()
    inp     = s.get('input_tokens_est', 0)
    out     = s.get('output_tokens_est', 0)
    t_saved = s.get('tokens_saved_session', 0)
    tool_s  = s.get('tool_savings_session', 0)
    out_s   = s.get('output_savings_session', 0)
    compact = s.get('compact_count_session', 0)
    limit   = s.get('context_limit', 200_000)
    mode    = s.get('mode', 'off')
    budget  = s.get('budget')
    total   = s.get('tokens_saved_total', 0)

    fill    = inp / limit if limit else 0
    w_total = inp + t_saved
    pct     = round(t_saved / w_total * 100) if w_total else 0

    print(f"""
╔══════════════════════════════════════════╗
║           PITH SESSION STATUS            ║
╚══════════════════════════════════════════╝

Context window:
  [{bar(fill)}]
  {fmt(inp)} / {fmt(limit)} ({round(fill*100)}% used)

Settings:
  Output mode:  {mode.upper()}
  Token budget: {"≤" + str(budget) + " tokens/response" if budget else "none"}

Token savings (this session):
  Tool output compression:  ~{fmt(tool_s)}
  Output style compression: ~{fmt(out_s)}
  Auto-compacts triggered:   {compact}x
  ─────────────────────────────────────────
  Total saved:              ~{fmt(t_saved)} tokens  (~{pct}% reduction)

Lifetime saved:             ~{fmt(total + t_saved)} tokens
""")

if __name__ == '__main__':
    main()
