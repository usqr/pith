#!/usr/bin/env python3
"""
Pith Evaluation Harness — honest token + quality measurement.

Three arms:
  __baseline__  — no system prompt
  __terse__     — "Answer concisely."
  pith          — "Answer concisely.\n\n{SKILL.md}"

Honest delta = pith vs terse (not pith vs baseline).
Baseline comparison conflates skill effect with generic terseness.

Plus correctness scoring via Claude-as-judge (optional, set PITH_EVAL_JUDGE=0 to skip).

Token counts: REAL values from Claude API usage field — not tiktoken approximation.

Run: uv run python evals/harness.py
Requires: ANTHROPIC_API_KEY
"""
from __future__ import annotations
import datetime as dt
import json
import os
import statistics
from pathlib import Path

EVALS  = Path(__file__).parent
SKILLS = EVALS.parent / 'skills'
PROMPTS_FILE  = EVALS / 'prompts' / 'en.txt'
SNAPSHOT_FILE = EVALS / 'snapshots' / 'results.json'
TERSE_PREFIX  = 'Answer concisely.'

JUDGE_PROMPT = """Evaluate this technical AI response.

Question: {question}
Response: {response}

Score 1-5 on each dimension:
- completeness: does it contain everything needed to act on it? (1=critical gaps, 5=complete)
- accuracy:     is it technically correct? (1=wrong, 5=correct)
- actionability: can the user immediately act on this? (1=cannot act, 5=immediately actionable)

Return JSON only, no explanation:
{{"completeness": N, "accuracy": N, "actionability": N, "missing": "brief note or empty string"}}"""


def call_claude(prompt: str, system: str | None, model: str) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    kwargs: dict = {
        'model': model, 'max_tokens': 2048,
        'messages': [{'role': 'user', 'content': prompt}],
    }
    if system: kwargs['system'] = system
    msg = client.messages.create(**kwargs)
    return {
        'text':          msg.content[0].text.strip(),
        'input_tokens':  msg.usage.input_tokens,
        'output_tokens': msg.usage.output_tokens,
    }


def judge(question: str, response: str, model: str) -> dict:
    try:
        r = call_claude(JUDGE_PROMPT.format(question=question, response=response), None, model)
        import re
        m = re.search(r'\{[\s\S]*\}', r['text'])
        return json.loads(m.group()) if m else {}
    except Exception as e:
        return {'completeness': -1, 'accuracy': -1, 'actionability': -1, 'missing': str(e)}


def main():
    prompts   = [p.strip() for p in PROMPTS_FILE.read_text().splitlines() if p.strip()]
    skills    = sorted(p.name for p in SKILLS.iterdir() if (p / 'SKILL.md').exists())
    model     = os.environ.get('PITH_EVAL_MODEL', 'claude-sonnet-4-6')
    run_judge = os.environ.get('PITH_EVAL_JUDGE', '1') != '0'

    print(f'Pith Eval — {len(prompts)} prompts × {len(skills) + 2} arms | model: {model} | judge: {run_judge}')

    snap: dict = {
        'metadata': {
            'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'model': model, 'n_prompts': len(prompts),
            'terse_prefix': TERSE_PREFIX, 'judge': run_judge,
            'note': 'Token counts are REAL values from Claude API usage field.',
        },
        'prompts': prompts,
        'arms': {},
    }

    def run_arm(name: str, system: str | None):
        print(f'\n  {name}', end='', flush=True)
        results = []
        for p in prompts:
            r = call_claude(p, system, model)
            if run_judge: r['judge'] = judge(p, r['text'], model)
            results.append(r)
            print('.', end='', flush=True)
        snap['arms'][name] = results

    run_arm('__baseline__', None)
    run_arm('__terse__',    TERSE_PREFIX)
    for skill in skills:
        md = (SKILLS / skill / 'SKILL.md').read_text()
        run_arm(skill, f'{TERSE_PREFIX}\n\n{md}')

    SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_FILE.write_text(json.dumps(snap, ensure_ascii=False, indent=2))
    print(f'\n\nWrote {SNAPSHOT_FILE}')


if __name__ == '__main__':
    main()
