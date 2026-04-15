#!/usr/bin/env python3
"""
Pith Benchmark — real API token measurement across compression modes.

Compares:
  normal    — "You are a helpful assistant."
  terse     — "Answer concisely."
  pith-lean — lean SKILL.md
  pith-ultra — ultra SKILL.md

Uses temperature=0, 3 trials per prompt for reproducibility.
Token counts from Claude API usage field (real, not approximated).

Run: uv run python benchmarks/run.py [--dry-run] [--update-readme]
Requires: ANTHROPIC_API_KEY
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_env = Path(__file__).parent.parent / '.env.local'
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

REPO    = Path(__file__).parent.parent
SKILLS  = REPO / 'skills'
RESULTS = Path(__file__).parent / 'results'

PROMPTS = [
    {'id': 'react-rerender',   'category': 'frontend',  'prompt': 'Why does my React component re-render on every parent render even with the same props?'},
    {'id': 'sql-injection',    'category': 'security',  'prompt': 'How do I prevent SQL injection in a Node.js application?'},
    {'id': 'postgres-index',   'category': 'database',  'prompt': 'What is the difference between a covering index and a partial index in PostgreSQL?'},
    {'id': 'git-rebase',       'category': 'git',       'prompt': 'What is the difference between git rebase and git merge?'},
    {'id': 'async-node',       'category': 'backend',   'prompt': 'How do I handle database transactions correctly with async/await in Node.js?'},
    {'id': 'microservices',    'category': 'arch',      'prompt': 'When should I use microservices versus a monolith?'},
    {'id': 'docker-size',      'category': 'devops',    'prompt': 'How do I reduce Docker image size using multi-stage builds?'},
    {'id': 'memory-leak',      'category': 'debugging', 'prompt': 'How do I debug a memory leak in a Node.js application?'},
    {'id': 'circuit-breaker',  'category': 'patterns',  'prompt': 'How do I implement a circuit breaker pattern in a microservice?'},
    {'id': 'test-mocking',     'category': 'testing',   'prompt': 'When should I mock dependencies in tests versus using real implementations?'},
]


def call_api(client, model: str, system: str, prompt: str, retries: int = 3) -> dict:
    import anthropic
    for attempt in range(retries + 1):
        try:
            r = client.messages.create(
                model=model, max_tokens=2048, temperature=0,
                system=system,
                messages=[{'role': 'user', 'content': prompt}],
            )
            return {'input_tokens': r.usage.input_tokens, 'output_tokens': r.usage.output_tokens, 'text': r.content[0].text}
        except anthropic.RateLimitError:
            if attempt < retries:
                time.sleep([5, 15, 30][min(attempt, 2)])
            else:
                raise


def run_benchmarks(client, model: str, modes: dict[str, str], trials: int) -> list:
    results = []
    for i, p in enumerate(PROMPTS, 1):
        entry = {'id': p['id'], 'category': p['category'], 'prompt': p['prompt']}
        for mode_name, system in modes.items():
            entry[mode_name] = []
            for t in range(1, trials + 1):
                print(f'  [{i}/{len(PROMPTS)}] {p["id"]} | {mode_name} | trial {t}/{trials}', file=sys.stderr)
                entry[mode_name].append(call_api(client, model, system, p['prompt']))
                time.sleep(0.5)
        results.append(entry)
    return results


def compute_stats(results: list, modes: list[str]) -> list:
    rows = []
    for entry in results:
        row = {'id': entry['id'], 'category': entry['category'], 'prompt': entry['prompt']}
        for mode in modes:
            tokens = [t['output_tokens'] for t in entry[mode]]
            row[f'{mode}_median'] = int(statistics.median(tokens))
        rows.append(row)
    return rows


def format_table(rows: list, modes: list[str]) -> str:
    header = '| Prompt | ' + ' | '.join(m.replace('-', ' ').title() for m in modes) + ' |'
    sep    = '|--------|' + '|'.join('---:' for _ in modes) + '|'
    lines  = [header, sep]
    for r in rows:
        cells = ' | '.join(str(r[f'{m}_median']) for m in modes)
        lines.append(f'| {r["id"]} | {cells} |')
    # Summary row
    avgs = {m: round(statistics.mean(r[f'{m}_median'] for r in rows)) for m in modes}
    avg_cells = ' | '.join(f'**{avgs[m]}**' for m in modes)
    lines.append(f'| **Average** | {avg_cells} |')
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--trials', type=int, default=3)
    p.add_argument('--model',  default='claude-sonnet-4-6')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--update-readme', action='store_true')
    args = p.parse_args()

    modes = {
        'normal':     'You are a helpful assistant.',
        'terse':      'Answer concisely.',
        'pith-lean':  'Answer concisely.\n\n' + (SKILLS / 'pith' / 'SKILL.md').read_text(),
        'pith-ultra': 'Answer concisely.\n\n' + (SKILLS / 'pith' / 'SKILL.md').read_text().replace('lean', 'ultra'),
    }

    if args.dry_run:
        print(f'Model: {args.model}  Trials: {args.trials}  Prompts: {len(PROMPTS)}')
        print(f'Total API calls: {len(PROMPTS) * len(modes) * args.trials}')
        for p_item in PROMPTS:
            print(f'  [{p_item["id"]}] {p_item["prompt"][:70]}')
        return

    import anthropic
    client = anthropic.Anthropic()

    print(f'Running: {len(PROMPTS)} prompts × {len(modes)} modes × {args.trials} trials = {len(PROMPTS)*len(modes)*args.trials} calls', file=sys.stderr)

    results = run_benchmarks(client, args.model, modes, args.trials)
    rows    = compute_stats(results, list(modes.keys()))
    table   = format_table(rows, list(modes.keys()))

    ts   = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    RESULTS.mkdir(parents=True, exist_ok=True)
    out  = RESULTS / f'benchmark_{ts}.json'
    out.write_text(json.dumps({'metadata': {'model': args.model, 'trials': args.trials, 'date': ts}, 'rows': rows, 'raw': results}, indent=2))
    print(f'\nResults saved: {out}', file=sys.stderr)
    print(table)


if __name__ == '__main__':
    main()
