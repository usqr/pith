#!/usr/bin/env python3
"""
Pith Setup — create wiki directory structure for a project.
Called by the onboarding skill after the user answers setup questions.

Usage:
    python3 setup.py --type greenfield --name "My App" --stack "Node/React/Postgres" --team solo
    python3 setup.py --type brownfield --name "Existing App" --pain "losing context"
"""
from __future__ import annotations
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

STATE   = Path.home() / '.pith' / 'state.json'
CWD_KEY = 'proj_' + re.sub(r'[^a-zA-Z0-9]', '', __import__('base64').b64encode(
    os.getcwd().encode()).decode())[:20]


def load_state() -> dict:
    try:
        if STATE.exists(): return json.loads(STATE.read_text())
    except Exception: pass
    return {}


def save_state(updates: dict):
    s = load_state()
    s[CWD_KEY] = {**s.get(CWD_KEY, {}), **updates}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2))


def create_wiki(project_type: str, name: str, stack: str, team: str, pain: str):
    cwd  = Path.cwd()
    wiki = cwd / 'wiki'
    raw  = cwd / 'raw' / 'sources'

    wiki.mkdir(exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)
    (wiki / 'entities').mkdir(exist_ok=True)
    (wiki / 'concepts').mkdir(exist_ok=True)
    (wiki / 'decisions').mkdir(exist_ok=True)

    now = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    # index.md
    (wiki / 'index.md').write_text(f"""# Wiki Index — {name}

_Maintained by Pith. Updated on every ingest._

## Entities
_(none yet)_

## Concepts
_(none yet)_

## Decisions
_(none yet)_

## Sources Processed
_(none yet)_
""")

    # log.md
    (wiki / 'log.md').write_text(f"""# Wiki Log

## [{now}] setup | Initial wiki created
Project: {name}
Type: {project_type}
Stack: {stack or 'unknown'}
Team: {team or 'unknown'}
""")

    # overview.md
    (wiki / 'overview.md').write_text(f"""# Project Overview — {name}

**Summary:** _(to be filled)_
**Stack:** {stack or 'to be determined'}
**Team:** {team or 'solo'}

## Architecture
_(to be filled as we build)_

## Key Components
_(to be filled)_

## Design Decisions
See [[decisions/]] directory.
""")

    # CLAUDE.md schema for wiki (placed in wiki dir)
    schema_src = Path(__file__).parent.parent / 'schemas' / 'wiki-claude.md'
    if schema_src.exists():
        import shutil
        shutil.copy(schema_src, wiki / 'CLAUDE.md')

    # Mark setup done in state
    save_state({
        'setup_done': True,
        'project_name': name,
        'project_type': project_type,
        'wiki_dir': str(wiki.relative_to(cwd)),
        'setup_date': now,
    })

    print(f"""Wiki created at {wiki}/

  wiki/
    index.md        ← catalog of all pages
    log.md          ← session history
    overview.md     ← project summary
    entities/       ← people, tools, services, components
    concepts/       ← ideas, patterns, methods
    decisions/      ← architecture decision records
  raw/sources/      ← drop source documents here

Setup complete. Pith will maintain the wiki as we work.""")


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--type',  default='greenfield', choices=['greenfield', 'brownfield'])
    p.add_argument('--name',  default='Project')
    p.add_argument('--stack', default='')
    p.add_argument('--team',  default='solo')
    p.add_argument('--pain',  default='')
    args = p.parse_args()
    create_wiki(args.type, args.name, args.stack, args.team, args.pain)

if __name__ == '__main__':
    main()
