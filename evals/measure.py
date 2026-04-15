#!/usr/bin/env python3
"""
Pith Measurement — analyze eval snapshot.

Uses REAL token counts from Claude API (not tiktoken approximation).
Reports skill vs terse delta — the honest comparison.
Includes quality scores if judge ran.

Run: python3 evals/measure.py
"""
from __future__ import annotations
import json
import statistics
from pathlib import Path

SNAPSHOT = Path(__file__).parent / 'snapshots' / 'results.json'


def pct(x: float) -> str:
    s = '−' if x < 0 else '+'
    return f'{s}{abs(x)*100:.0f}%'


def score_str(vals: list) -> str:
    good = [v for v in vals if isinstance(v, (int, float)) and v > 0]
    return f'{statistics.mean(good):.1f}/5' if good else 'n/a'


def main():
    if not SNAPSHOT.exists():
        print(f'No snapshot at {SNAPSHOT}. Run harness.py first.'); return

    data  = json.loads(SNAPSHOT.read_text())
    arms  = data['arms']
    meta  = data.get('metadata', {})
    n     = meta.get('n_prompts', '?')
    model = meta.get('model', '?')

    print(f'Model: {model}  |  n={n} prompts  |  Generated: {meta.get("generated_at","?")}')
    print(f'Token source: REAL (Claude API usage.output_tokens)')
    print(f'Delta baseline: pith vs terse (honest — isolates skill contribution)\n')

    # Reference arms
    def total_out(arm): return sum(r['output_tokens'] for r in arm)
    bl_t = total_out(arms['__baseline__'])
    te_t = total_out(arms['__terse__'])
    print(f'Reference arms (output tokens total):')
    print(f'  baseline:  {bl_t:,}')
    print(f'  terse:     {te_t:,}  ({pct(1 - te_t/bl_t)} vs baseline)\n')

    has_judge = meta.get('judge') and arms['__baseline__'][0].get('judge')
    if has_judge:
        print('| Skill | vs terse | median | stdev | complete | accurate | actable |')
        print('|-------|---------|--------|-------|----------|----------|---------|')
    else:
        print('| Skill | vs terse | median | mean | stdev |')
        print('|-------|---------|--------|------|-------|')

    rows = []
    for name, results in arms.items():
        if name.startswith('__'): continue
        tokens = [r['output_tokens'] for r in results]
        terse_tokens = [r['output_tokens'] for r in arms['__terse__']]
        savings = [1 - s/t if t else 0 for s, t in zip(tokens, terse_tokens)]
        med  = statistics.median(savings)
        mean = statistics.mean(savings)
        sd   = statistics.stdev(savings) if len(savings) > 1 else 0.0

        row = {'name': name, 'med': med, 'mean': mean, 'sd': sd}
        if has_judge:
            row['complete']    = score_str([r['judge'].get('completeness',   -1) for r in results])
            row['accuracy']    = score_str([r['judge'].get('accuracy',       -1) for r in results])
            row['actionable']  = score_str([r['judge'].get('actionability',  -1) for r in results])
        rows.append(row)

    for r in sorted(rows, key=lambda x: -x['med']):
        if has_judge:
            print(f"| **{r['name']}** | {pct(r['med'])} | {r['med']*100:.0f}% | {r['sd']*100:.0f}% "
                  f"| {r['complete']} | {r['accuracy']} | {r['actionable']} |")
        else:
            print(f"| **{r['name']}** | {pct(r['med'])} | {r['med']*100:.0f}% "
                  f"| {r['mean']*100:.0f}% | {r['sd']*100:.0f}% |")

    print(f'\n_Delta = 1 - skill_tokens/terse_tokens. Positive = fewer tokens than terse control._')
    if has_judge: print('_Quality: Claude-as-judge, 1-5. Measures completeness + accuracy + actionability._')


if __name__ == '__main__':
    main()
