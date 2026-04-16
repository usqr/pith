#!/usr/bin/env python3
"""
Pith Telemetry — show every compression event with before/after content.

Usage:
    python3 tools/telemetry.py              # all events this session
    python3 tools/telemetry.py --all        # all sessions
    python3 tools/telemetry.py --tail       # last 20 events
    python3 tools/telemetry.py --watch      # live tail (poll every 2s)
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

TELEMETRY = Path.home() / '.pith' / 'telemetry.jsonl'
STATE     = Path.home() / '.pith' / 'state.json'
W         = 80

# ── colour codes ──────────────────────────────────────────────────────────────
GREEN  = '\033[32m'
YELLOW = '\033[33m'
CYAN   = '\033[36m'
DIM    = '\033[2m'
BOLD   = '\033[1m'
RED    = '\033[31m'
RESET  = '\033[0m'

def c(code, text):
    return code + text + RESET if sys.stdout.isatty() else text


# ── helpers ──────────────────────────────────────────────────────────────────

def load_events(all_sessions=False):
    if not TELEMETRY.exists():
        return []
    events = []
    for line in TELEMETRY.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except Exception:
            pass
    if all_sessions:
        return events
    # Filter to current session
    session = current_session()
    if session:
        return [e for e in events if e.get('session') == session]
    # Fallback: last 60 minutes
    import datetime
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(minutes=60)).isoformat()
    return [e for e in events if e.get('ts', '') >= cutoff]


def current_session():
    try:
        state = json.loads(STATE.read_text())
        # Find the project key for cwd
        cwd = os.getcwd()
        import base64, re
        key = 'proj_' + re.sub(r'[^a-zA-Z0-9]', '', base64.b64encode(cwd.encode()).decode())[:20]
        return state.get(key, {}).get('session_start', '')
    except Exception:
        return ''


def bar(pct, width=20):
    filled = max(0, min(width, round(pct / 100 * width)))
    colour = GREEN if pct >= 40 else YELLOW if pct >= 20 else DIM
    return c(colour, '█' * filled) + c(DIM, '░' * (width - filled))


def fmt_tokens(n):
    if n >= 1000:
        return f'{n/1000:.1f}k'
    return str(n)


def trunc(text, width):
    if len(text) <= width:
        return text
    return text[:width - 3] + '...'


# ── display ──────────────────────────────────────────────────────────────────

def header():
    print(c(BOLD, '━' * W))
    print(c(BOLD, '  PITH COMPRESSION TELEMETRY'))
    print(c(BOLD, '━' * W))
    print(f'  Log: {TELEMETRY}')
    print()


def summary(events):
    if not events:
        print(c(DIM, '  No compression events this session yet.'))
        print(c(DIM, '  Compression fires automatically when tool output exceeds 30 lines.'))
        return

    total_before = sum(e['before_tokens'] for e in events)
    total_after  = sum(e['after_tokens']  for e in events)
    total_saved  = total_before - total_after
    overall_pct  = round(total_saved / total_before * 100) if total_before else 0

    print(c(BOLD, f'  SESSION SUMMARY  ({len(events)} compressions)'))
    print()
    print(f'  {bar(overall_pct)}  {overall_pct}% saved  '
          f'({c(RED, fmt_tokens(total_before))} → {c(GREEN, fmt_tokens(total_after))}  '
          f'saved {c(GREEN, fmt_tokens(total_saved))} tokens)')
    print()


def event_table(events):
    if not events:
        return
    # Header row
    print(c(DIM, f"  {'TIME':<8}  {'TOOL':<6}  {'FILE / COMMAND':<30}  "
                 f"{'BEFORE':>7}  {'AFTER':>6}  {'SAVED':>6}  {'BAR':<22}"))
    print(c(DIM, '  ' + '─' * (W - 2)))

    for e in events:
        ts    = e.get('ts', '')[-8:-3]          # HH:MM
        tool  = e.get('tool', '')[:6]
        label = trunc(Path(e.get('label', '')).name or e.get('label', ''), 30)
        bl    = e['before_tokens']
        al    = e['after_tokens']
        pct   = e['saved_pct']
        b     = bar(pct, 18)

        colour = GREEN if pct >= 40 else YELLOW if pct >= 20 else DIM
        print(f"  {c(DIM, ts):<8}  {c(CYAN, tool):<6}  {label:<30}  "
              f"{c(RED, fmt_tokens(bl)):>7}  {c(GREEN, fmt_tokens(al)):>6}  "
              f"{c(colour, str(pct)+'%'):>6}  {b}")

    print()


def event_detail(events, n=5):
    """Show last N events with actual before/after content."""
    if not events:
        return
    shown = events[-n:]
    print(c(BOLD, f'  LAST {len(shown)} COMPRESSIONS — BEFORE vs AFTER'))
    print()

    for e in shown:
        ts    = e.get('ts', '')[:19].replace('T', ' ')
        label = e.get('label', 'unknown')
        pct   = e['saved_pct']
        bl    = e['before_lines']
        al    = e['after_lines']
        bt    = e['before_tokens']
        at_   = e['after_tokens']

        print(c(BOLD, f'  [{ts}]  {e["tool"].upper()} — {trunc(label, 50)}'))
        print(f'  {c(RED, str(bl) + " lines / " + fmt_tokens(bt) + " tok")} → '
              f'{c(GREEN, str(al) + " lines / " + fmt_tokens(at_) + " tok")}  '
              f'({c(GREEN, str(pct) + "% saved")})')
        print()

        bh = e.get('before_head', '').replace('\n', '\n  │  ')
        ah = e.get('after_head',  '').replace('\n', '\n  │  ')

        print(c(DIM,  f'  ┌─ BEFORE (what the tool returned)'))
        print(c(DIM,  f'  │  {bh}'))
        print(c(DIM,  f'  │  ... ({bl} lines total)'))
        print()
        print(c(GREEN, f'  ┌─ AFTER  (what Claude sees)'))
        print(c(GREEN, f'  │  {ah}'))
        print(c(GREEN, f'  │  ... ({al} lines total)'))
        print()
        print(c(DIM, '  ' + '─' * (W - 2)))
        print()


# ── watch mode ───────────────────────────────────────────────────────────────

def watch():
    last_count = 0
    print(c(BOLD, 'Watching for compression events — Ctrl+C to stop'))
    print()
    while True:
        events = load_events()
        if len(events) != last_count:
            new = events[last_count:]
            for e in new:
                label = trunc(Path(e.get('label', '')).name or e.get('label', ''), 35)
                pct   = e['saved_pct']
                bt    = e['before_tokens']
                at_   = e['after_tokens']
                colour = GREEN if pct >= 40 else YELLOW if pct >= 20 else DIM
                print(f'  {c(CYAN, e["tool"][:5]):<5}  {label:<35}  '
                      f'{c(RED, fmt_tokens(bt))} → {c(GREEN, fmt_tokens(at_))}  '
                      f'{bar(pct, 14)}  {c(colour, str(pct) + "%")}')
            last_count = len(events)
        time.sleep(2)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description='Pith compression telemetry viewer')
    p.add_argument('--all',   action='store_true', help='All sessions, not just current')
    p.add_argument('--tail',  type=int, default=0, metavar='N', help='Show last N events (default 20)')
    p.add_argument('--watch', action='store_true', help='Live tail — print new events as they arrive')
    args = p.parse_args()

    if args.watch:
        watch()
        return

    events = load_events(all_sessions=args.all)

    if args.tail:
        events = events[-args.tail:]
    elif not args.all and len(events) > 50:
        events = events[-50:]

    header()
    summary(events)
    event_table(events)
    event_detail(events, n=min(5, len(events)))

    if not events:
        print(c(DIM, '  Tip: run  /pith status  inside a Claude Code session to see live counts.'))
        print()


if __name__ == '__main__':
    main()
