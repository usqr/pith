#!/usr/bin/env python3
"""
Pith Session Report — generates a standalone HTML dashboard showing
token flow, compression breakdown, and cost metrics for the current session.

Writes to ~/.pith/report.html and opens it in the browser.
Usage:  python3 report.py          # generate and open
        python3 report.py --no-open  # generate only
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import re
import webbrowser
from pathlib import Path

STATE     = Path.home() / '.pith' / 'state.json'
TELEMETRY = Path.home() / '.pith' / 'telemetry.jsonl'
OUTPUT    = Path.home() / '.pith' / 'report.html'

IN_COST_PER_M  = 3.0   # Sonnet 4.6 input  $/1M tokens
OUT_COST_PER_M = 15.0  # Sonnet 4.6 output $/1M tokens


def load_state() -> dict:
    try:
        if STATE.exists():
            d = json.loads(STATE.read_text())
            cwd_key = 'proj_' + re.sub(r'[^a-zA-Z0-9]', '',
                      base64.b64encode(os.getcwd().encode()).decode())[:20]
            return d.get(cwd_key, {})
    except Exception:
        pass
    return {}


def load_telemetry(session_start: str) -> list[dict]:
    events: list[dict] = []
    if not TELEMETRY.exists():
        return events
    for line in TELEMETRY.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
            if not session_start or e.get('session', '') == session_start:
                events.append(e)
        except Exception:
            pass
    return events


def generate_html(s: dict, events: list[dict]) -> str:
    inp       = s.get('input_tokens_est', 0)
    out_tok   = s.get('output_tokens_est', 0)
    t_saved   = s.get('tokens_saved_session', 0)
    toon_s    = s.get('toon_savings_session', 0)
    skel_s    = s.get('skeleton_savings_session', 0)
    bash_s    = s.get('bash_savings_session', 0)
    grep_s    = s.get('grep_savings_session', 0)
    web_s     = s.get('web_savings_session', 0)
    offload_s = s.get('offload_savings_session', 0)
    out_s     = s.get('output_savings_session', 0)
    limit     = s.get('context_limit', 200_000)
    mode      = s.get('mode', 'off')

    without   = inp + t_saved
    pct       = round(t_saved / without * 100) if without else 0
    fill_pct  = round(inp / limit * 100) if limit else 0

    actual_in_cost  = inp     / 1_000_000 * IN_COST_PER_M
    actual_out_cost = out_tok / 1_000_000 * OUT_COST_PER_M
    actual_cost     = actual_in_cost + actual_out_cost

    tool_saved     = t_saved - out_s
    saved_in_cost  = tool_saved / 1_000_000 * IN_COST_PER_M
    saved_out_cost = out_s      / 1_000_000 * OUT_COST_PER_M
    saved_cost     = saved_in_cost + saved_out_cost
    would_cost     = actual_cost + saved_cost

    comp_ratio = round(without / inp, 2) if inp > 0 else 1.0
    roi        = round(saved_cost / actual_cost, 2) if actual_cost > 0.00001 else 0.0

    # Per-event telemetry timeline (last 30)
    tel_labels = json.dumps([e.get('ts', '')[-8:-3] for e in events[-30:]])
    tel_saved  = json.dumps([e.get('before_tokens', 0) - e.get('after_tokens', 0) for e in events[-30:]])
    tel_after  = json.dumps([e.get('after_tokens', 0) for e in events[-30:]])

    buckets_labels = json.dumps([
        'Skeletons', 'Bash/build', 'Grep', 'TOON', 'Web', 'Offloaded', 'Output mode'
    ])
    buckets_data = json.dumps([skel_s, bash_s, grep_s, toon_s, web_s, offload_s, out_s])

    def fc(n: float) -> str:
        return f'${n:.4f}' if n >= 0.0001 else '<$0.0001'

    def fk(n: int) -> str:
        if n >= 1_000_000: return f'{n/1_000_000:.1f}M'
        if n >= 1_000:     return f'{n/1_000:.1f}k'
        return str(n)

    session_date = s.get('session_start', 'this session')[:19].replace('T', ' ')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Pith Session Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --bg:      #09090b;
  --surface: #111113;
  --border:  rgba(255,255,255,0.08);
  --text:    #e4e4e7;
  --muted:   #71717a;
  --dim:     #3f3f46;
  --purple:  #a78bfa;
  --green:   #34d399;
  --yellow:  #fbbf24;
  --red:     #f87171;
}}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: 'SF Mono', 'Fira Code', ui-monospace, monospace;
  font-size: 13px;
  min-height: 100vh;
  padding: 32px 24px;
}}
h1 {{ font-size: 15px; font-weight: 700; color: var(--purple); letter-spacing: 0.1em; }}
.subtitle {{ color: var(--muted); font-size: 11px; margin-top: 4px; }}
header {{ margin-bottom: 28px; }}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}}
.card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px 20px;
}}
.card-title {{
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 10px;
}}
.big {{ font-size: 26px; font-weight: 700; }}
.sub {{ font-size: 11px; color: var(--muted); margin-top: 4px; }}
.green  {{ color: var(--green); }}
.yellow {{ color: var(--yellow); }}
.red    {{ color: var(--red); }}
.purple {{ color: var(--purple); }}

/* flow bar */
.flow {{ margin: 6px 0; }}
.flow-label {{ font-size: 10px; color: var(--muted); width: 140px; display: inline-block; }}
.flow-track {{
  display: inline-block;
  width: 180px;
  height: 8px;
  background: var(--dim);
  border-radius: 4px;
  vertical-align: middle;
  overflow: hidden;
  margin-right: 8px;
}}
.flow-fill {{
  height: 100%;
  border-radius: 4px;
  transition: width 0.6s ease;
}}
.flow-val {{ font-size: 10px; color: var(--muted); }}

.wide {{ grid-column: 1 / -1; }}
canvas {{ max-height: 220px; }}

table {{ width: 100%; border-collapse: collapse; font-size: 11px; margin-top: 6px; }}
th {{ color: var(--muted); text-align: left; padding: 4px 6px; font-weight: normal; border-bottom: 1px solid var(--border); }}
td {{ padding: 5px 6px; border-bottom: 1px solid var(--dim); }}
tr:last-child td {{ border-bottom: none; }}

footer {{ color: var(--muted); font-size: 10px; margin-top: 28px; text-align: center; }}
</style>
</head>
<body>
<header>
  <h1>◆ PITH SESSION REPORT</h1>
  <div class="subtitle">{session_date} &nbsp;·&nbsp; mode: {mode.upper()} &nbsp;·&nbsp; Sonnet 4.6</div>
</header>

<!-- ── KPI cards ── -->
<div class="grid">

  <div class="card">
    <div class="card-title">Compression Ratio</div>
    <div class="big purple">{comp_ratio}:1</div>
    <div class="sub">{pct}% fewer tokens than uncompressed baseline</div>
  </div>

  <div class="card">
    <div class="card-title">Tokens Saved</div>
    <div class="big green">{fk(t_saved)}</div>
    <div class="sub">of {fk(without)} token baseline removed by Pith</div>
  </div>

  <div class="card">
    <div class="card-title">Cost ROI</div>
    <div class="big {'green' if roi > 1 else 'yellow'}">{roi}×</div>
    <div class="sub">{fc(saved_cost)} saved · {fc(actual_cost)} spent</div>
  </div>

  <div class="card">
    <div class="card-title">Context Fill</div>
    <div class="big {'red' if fill_pct > 85 else 'yellow' if fill_pct > 70 else 'green'}">{fill_pct}%</div>
    <div class="sub">{fk(inp)} of {fk(limit)} tokens used</div>
  </div>

</div>

<!-- ── Token flow ── -->
<div class="card" style="margin-bottom:16px">
  <div class="card-title">Token Flow</div>

  <div class="flow">
    <span class="flow-label">Baseline (no Pith)</span>
    <span class="flow-track"><span class="flow-fill" style="width:100%;background:#3f3f46"></span></span>
    <span class="flow-val">{fk(without)}</span>
  </div>
  <div class="flow">
    <span class="flow-label">Pith intercepted</span>
    <span class="flow-track"><span class="flow-fill" style="width:{round(t_saved/without*100) if without else 0}%;background:#a78bfa"></span></span>
    <span class="flow-val purple">-{fk(t_saved)}</span>
  </div>
  <div class="flow">
    <span class="flow-label">Sent to context (input)</span>
    <span class="flow-track"><span class="flow-fill" style="width:{round(inp/without*100) if without else 0}%;background:#818cf8"></span></span>
    <span class="flow-val">{fk(inp)}</span>
  </div>
  <div class="flow">
    <span class="flow-label">Model output</span>
    <span class="flow-track"><span class="flow-fill" style="width:{round(out_tok/without*100) if without else 0}%;background:#fbbf24"></span></span>
    <span class="flow-val yellow">{fk(out_tok)}</span>
  </div>
</div>

<!-- ── Charts row ── -->
<div class="grid">

  <div class="card">
    <div class="card-title">Savings by Category</div>
    <canvas id="donut"></canvas>
  </div>

  <div class="card">
    <div class="card-title">Input vs Output vs Saved</div>
    <canvas id="bar"></canvas>
  </div>

  {'<div class="card wide"><div class="card-title">Compression Events Timeline</div><canvas id="timeline"></canvas></div>' if events else ''}

</div>

<!-- ── Cost table ── -->
<div class="card" style="margin-bottom:16px">
  <div class="card-title">Cost Breakdown</div>
  <table>
    <thead><tr><th>Item</th><th>Tokens</th><th>Cost</th></tr></thead>
    <tbody>
      <tr><td>Input tokens</td><td>{fk(inp)}</td><td>{fc(actual_in_cost)}</td></tr>
      <tr><td>Output tokens</td><td>{fk(out_tok)}</td><td>{fc(actual_out_cost)}</td></tr>
      <tr><td class="yellow">Actual spend</td><td>—</td><td class="yellow">{fc(actual_cost)}</td></tr>
      <tr><td class="green">Tool compression saved</td><td>-{fk(tool_saved)}</td><td class="green">-{fc(saved_in_cost)}</td></tr>
      <tr><td class="green">Output mode saved</td><td>-{fk(out_s)}</td><td class="green">-{fc(saved_out_cost)}</td></tr>
      <tr><td class="green">Total saved</td><td>-{fk(t_saved)}</td><td class="green">-{fc(saved_cost)}</td></tr>
      <tr><td class="red">Without Pith</td><td>{fk(without)}</td><td class="red">{fc(would_cost)}</td></tr>
    </tbody>
  </table>
</div>

<footer>Generated by Pith · /pith report · {session_date}</footer>

<script>
const PURPLE = '#a78bfa', GREEN = '#34d399', YELLOW = '#fbbf24', RED = '#f87171';
const BLUE = '#818cf8', ORANGE = '#fb923c', PINK = '#f472b6', CYAN = '#22d3ee';

Chart.defaults.color = '#71717a';
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
Chart.defaults.font.family = "'SF Mono', 'Fira Code', ui-monospace, monospace";
Chart.defaults.font.size = 11;

// ── Donut — savings by category ──
const bucketLabels = {buckets_labels};
const bucketData   = {buckets_data};
const bucketColors = [BLUE, ORANGE, CYAN, PURPLE, PINK, GREEN, YELLOW];
const nonZeroLabels = [], nonZeroData = [], nonZeroColors = [];
bucketLabels.forEach((l, i) => {{
  if (bucketData[i] > 0) {{
    nonZeroLabels.push(l);
    nonZeroData.push(bucketData[i]);
    nonZeroColors.push(bucketColors[i]);
  }}
}});

new Chart(document.getElementById('donut'), {{
  type: 'doughnut',
  data: {{
    labels: nonZeroLabels.length ? nonZeroLabels : ['No data'],
    datasets: [{{ data: nonZeroData.length ? nonZeroData : [1], backgroundColor: nonZeroColors.length ? nonZeroColors : ['#3f3f46'], borderWidth: 0 }}]
  }},
  options: {{
    cutout: '65%',
    plugins: {{ legend: {{ position: 'right', labels: {{ boxWidth: 10, padding: 12 }} }} }},
    animation: {{ duration: 700 }}
  }}
}});

// ── Bar — input / output / saved ──
new Chart(document.getElementById('bar'), {{
  type: 'bar',
  data: {{
    labels: ['Input', 'Output', 'Saved'],
    datasets: [{{
      data: [{inp}, {out_tok}, {t_saved}],
      backgroundColor: [BLUE, YELLOW, GREEN],
      borderRadius: 4,
      borderWidth: 0,
    }}]
  }},
  options: {{
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ beginAtZero: true, ticks: {{ callback: v => v >= 1000 ? (v/1000).toFixed(1)+'k' : v }} }},
      x: {{ grid: {{ display: false }} }}
    }},
    animation: {{ duration: 700 }}
  }}
}});

// ── Timeline — compression events ──
{f"""new Chart(document.getElementById('timeline'), {{
  type: 'bar',
  data: {{
    labels: {tel_labels},
    datasets: [
      {{ label: 'After (kept)', data: {tel_after},  backgroundColor: BLUE,   borderRadius: 2, borderWidth: 0 }},
      {{ label: 'Saved',        data: {tel_saved}, backgroundColor: GREEN,  borderRadius: 2, borderWidth: 0 }}
    ]
  }},
  options: {{
    plugins: {{ legend: {{ position: 'top', labels: {{ boxWidth: 10 }} }} }},
    scales: {{
      x: {{ stacked: true, grid: {{ display: false }} }},
      y: {{ stacked: true, beginAtZero: true, ticks: {{ callback: v => v >= 1000 ? (v/1000).toFixed(1)+'k' : v }} }}
    }},
    animation: {{ duration: 700 }}
  }}
}});""" if events else '// no telemetry events'}
</script>
</body>
</html>"""


def main():
    p = argparse.ArgumentParser(description='Pith session report generator')
    p.add_argument('--no-open', action='store_true', help='Generate but do not open in browser')
    args = p.parse_args()

    s         = load_state()
    session   = s.get('session_start', '')
    events    = load_telemetry(session)
    html      = generate_html(s, events)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding='utf-8')
    print(f'[PITH REPORT] written → {OUTPUT}')

    if not args.no_open:
        url = OUTPUT.resolve().as_uri()
        webbrowser.open(url)
        print(f'[PITH REPORT] opening {url}')


if __name__ == '__main__':
    main()
