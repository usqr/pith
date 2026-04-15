#!/usr/bin/env python3
"""
Pith Compact — summarize conversation history to reduce context.
Called internally when auto-compact threshold is reached.

Usage:
    python3 compact.py --stdin          # read messages JSON from stdin
    python3 compact.py --file <path>    # read messages JSON from file
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROMPT = """Summarize this AI coding session into a structured document for seamless continuation.

PRESERVE EXACTLY (reproduce verbatim):
- All file paths and directory structure discussed
- All error messages (exact text)
- All code snippets written or reviewed
- All terminal commands used
- All decisions made and their reasons

OUTPUT THIS STRUCTURE:

## Session Context
[1-2 sentences: current task and where we are]

## Files In Progress
[Each file: path | current state | what changed]

## Decisions Made
- [decision] — [reason]

## Errors Encountered
[Error message exactly] — Status: resolved | unresolved — Fix: [if resolved]

## Code Written
```[lang]
[code exactly]
```

## Open Questions / Next Steps
- [what's unresolved]
- [immediate next action]

Eliminate all conversational filler. Keep only technical substance.

CONVERSATION:
{conversation}"""


def call_claude(prompt: str) -> str:
    if key := os.environ.get('ANTHROPIC_API_KEY'):
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            msg = client.messages.create(
                model=os.environ.get('PITH_MODEL', 'claude-sonnet-4-6'),
                max_tokens=4096,
                messages=[{'role': 'user', 'content': prompt}],
            )
            return msg.content[0].text.strip()
        except ImportError:
            pass
    try:
        r = subprocess.run(['claude', '--print'], input=prompt, text=True,
                           capture_output=True, check=True, timeout=60)
        return r.stdout.strip()
    except Exception as e:
        raise RuntimeError(f'Claude call failed: {e}')


def format_messages(messages: list) -> str:
    parts = []
    for m in messages:
        role    = m.get('role', 'unknown').upper()
        content = m.get('content', '')
        if isinstance(content, list):
            content = '\n'.join(
                p.get('text', '') for p in content
                if isinstance(p, dict) and p.get('type') == 'text'
            )
        if content.strip():
            parts.append(f'[{role}]\n{content}')
    return '\n\n'.join(parts)


def compact(messages: list) -> str:
    convo = format_messages(messages)
    if not convo.strip():
        return '[PITH COMPACT: no content to compact]'
    return call_claude(PROMPT.format(conversation=convo))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--stdin',  action='store_true')
    p.add_argument('--file',   default='')
    args = p.parse_args()

    if args.file:
        data = json.loads(Path(args.file).read_text())
    else:
        data = json.loads(sys.stdin.read())

    messages = data if isinstance(data, list) else data.get('messages', [])
    print(compact(messages))

if __name__ == '__main__':
    main()
