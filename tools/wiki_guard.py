#!/usr/bin/env python3
"""
Pith Wiki Guard — cross-references files against wiki/decisions/ and flags violations.

Usage:
  python3 wiki_guard.py --file <path> [--snippet <text>]   # check single file
  python3 wiki_guard.py --scan                              # check all staged/modified files
  python3 wiki_guard.py --json                              # output JSON instead of text
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ── Tech → violation rules ────────────────────────────────────────────────────
# Keys: lowercase tech name as it appears in decision files.
# Aliases handle common variations ("tailwind" vs "tailwind css").

TECH_RULES: dict[str, dict] = {
    'tailwind css': {
        'bad_ext':     {'.css', '.scss', '.sass', '.less'},
        'allow_names': {'globals.css', 'global.css', 'reset.css', 'base.css'},
        'bad_imports': [],
        'msg': 'Custom stylesheet detected. Decision mandates Tailwind utility classes only.',
    },
    'tailwind': {
        'bad_ext':     {'.css', '.scss', '.sass', '.less'},
        'allow_names': {'globals.css', 'global.css', 'reset.css', 'base.css'},
        'bad_imports': [],
        'msg': 'Custom stylesheet detected. Decision mandates Tailwind utility classes only.',
    },
    'shadcn/ui': {
        'bad_ext':     set(),
        'allow_names': set(),
        'bad_imports': [
            '@mui/', '@emotion/', '@chakra-ui/', 'antd', '@ant-design/',
            'react-bootstrap', 'bootstrap/', 'mantine', '@mantine/',
            'flowbite', 'daisyui', 'primereact', 'rsuite',
        ],
        'msg': 'Third-party component library detected. Decision mandates shadcn/ui.',
    },
    'shadcn': {
        'bad_ext':     set(),
        'allow_names': set(),
        'bad_imports': [
            '@mui/', '@emotion/', '@chakra-ui/', 'antd', '@ant-design/',
            'react-bootstrap', 'bootstrap/', 'mantine', '@mantine/',
        ],
        'msg': 'Third-party component library detected. Decision mandates shadcn/ui.',
    },
    'next.js': {
        'bad_ext':     set(),
        'allow_names': set(),
        'bad_imports': [
            'react-router', 'react-router-dom', '@reach/router',
            'wouter', '@tanstack/react-router',
        ],
        'msg': 'Client-side router detected. Decision mandates Next.js App Router.',
    },
    'next': {
        'bad_ext':     set(),
        'allow_names': set(),
        'bad_imports': ['react-router', 'react-router-dom', '@reach/router', 'wouter'],
        'msg': 'Client-side router detected. Decision mandates Next.js App Router.',
    },
    'postgresql': {
        'bad_ext':     set(),
        'allow_names': set(),
        'bad_imports': ['sqlite3', 'better-sqlite3', 'mysql2', 'mongoose', 'mongodb'],
        'msg': 'Non-Postgres database client detected.',
    },
    'typescript': {
        'bad_ext':     {'.js', '.jsx'},
        'allow_names': set(),
        'bad_imports': [],
        'msg': 'Plain JS file in a TypeScript project.',
    },
}

# File extensions worth scanning for imports
IMPORT_EXTS = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.py', '.go', '.java'}
# Extensions to skip entirely (binaries, generated)
SKIP_EXTS   = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.woff2',
               '.ttf', '.eot', '.lock', '.sum', '.map', '.min.js', '.min.css'}


def load_decisions(wiki_dir: Path) -> list[dict]:
    """Parse all decision files and extract mandated technologies."""
    decisions = []
    if not wiki_dir.exists():
        return decisions
    for f in sorted(wiki_dir.glob('*.md')):
        try:
            d = parse_decision(f.name, f.read_text(errors='ignore'))
            if d:
                decisions.append(d)
        except Exception:
            pass
    return decisions


def parse_decision(filename: str, content: str) -> dict | None:
    """Extract title, date, and mandated techs from a decision markdown file."""
    title_m = re.search(r'^#\s+Decision:\s*(.+)', content, re.MULTILINE)
    title   = title_m.group(1).strip() if title_m else filename.replace('.md', '')
    date_m  = re.search(r'\*\*Date:\*\*\s*(\S+)', content, re.IGNORECASE)
    date    = date_m.group(1) if date_m else '?'

    lower   = content.lower()
    techs   = set()

    # Table cells: | Styling | Tailwind CSS |
    for m in re.finditer(r'\|\s*([^|\n]+)\s*\|', content):
        cell = m.group(1).strip().lower()
        for tech in TECH_RULES:
            if tech in cell:
                techs.add(tech)

    # **Bold** mentions
    for m in re.finditer(r'\*\*([^*\n]+)\*\*', content):
        term = m.group(1).strip().lower()
        for tech in TECH_RULES:
            if tech in term:
                techs.add(tech)

    # Plain prose
    for tech in TECH_RULES:
        if tech in lower:
            techs.add(tech)

    # De-duplicate: prefer specific keys ("tailwind css") over aliases ("tailwind")
    if 'tailwind css' in techs:
        techs.discard('tailwind')
    if 'shadcn/ui' in techs:
        techs.discard('shadcn')
    if 'next.js' in techs:
        techs.discard('next')

    if not techs:
        return None
    return {'title': title, 'file': filename, 'techs': sorted(techs), 'date': date}


def check_file(filepath: str, snippet: str, decisions: list[dict]) -> list[dict]:
    """Check a file path + content snippet against all loaded decisions."""
    violations = []
    path = Path(filepath)
    ext  = path.suffix.lower()
    name = path.name.lower()

    # Skip binary / generated files
    if ext in SKIP_EXTS or name.endswith('.min.js') or name.endswith('.min.css'):
        return violations

    seen = set()  # deduplicate: one violation per (file, decision)

    for decision in decisions:
        key_prefix = decision['file']
        for tech in decision['techs']:
            rule = TECH_RULES.get(tech)
            if not rule:
                continue

            # Extension check
            if ext in rule.get('bad_ext', set()):
                if name not in rule.get('allow_names', set()):
                    key = (filepath, key_prefix, 'ext')
                    if key not in seen:
                        seen.add(key)
                        violations.append({
                            'file': filepath,
                            'decision': decision['title'],
                            'decision_file': decision['file'],
                            'date': decision['date'],
                            'reason': rule['msg'],
                            'kind': 'extension',
                        })

            # Import check (only for source files)
            if ext in IMPORT_EXTS and snippet:
                for bad in rule.get('bad_imports', []):
                    if bad in snippet:
                        key = (filepath, key_prefix, bad)
                        if key not in seen:
                            seen.add(key)
                            violations.append({
                                'file': filepath,
                                'decision': decision['title'],
                                'decision_file': decision['file'],
                                'date': decision['date'],
                                'reason': f'Import `{bad}` found. {rule["msg"]}',
                                'kind': 'import',
                            })

    return violations


def format_violations(violations: list[dict], color: bool = True) -> str:
    """Format as human-readable warning block."""
    if not violations:
        return ''

    R  = '\033[0m'  if color else ''
    YL = '\033[93m' if color else ''
    RD = '\033[91m' if color else ''
    CY = '\033[96m' if color else ''
    GY = '\033[90m' if color else ''
    B  = '\033[1m'  if color else ''

    lines = [f'{YL}{B}⚠  WIKI GUARD — {len(violations)} violation(s) detected{R}']
    lines.append(f'{GY}{"─" * 52}{R}')
    for v in violations:
        lines.append(f'{RD}CONFLICT{R}  {B}{v["file"]}{R}')
        lines.append(f'  {GY}Decision :{R} {v["decision"]}  {GY}({v["date"]}){R}')
        lines.append(f'  {GY}Reason   :{R} {v["reason"]}')
        lines.append(f'  {CY}→ /pith wiki "{v["decision_file"].replace(".md", "")}"{R}')
        lines.append('')
    return '\n'.join(lines)


def get_staged_files() -> list[str]:
    """Return staged + modified file paths from git."""
    try:
        r1 = subprocess.run(['git', 'diff', '--name-only', '--cached'],
                            capture_output=True, text=True, timeout=5)
        r2 = subprocess.run(['git', 'diff', '--name-only'],
                            capture_output=True, text=True, timeout=5)
        files = set(r1.stdout.strip().splitlines() + r2.stdout.strip().splitlines())
        return [f for f in files if f]
    except Exception:
        return []


def read_snippet(filepath: str, lines: int = 60) -> str:
    """Read first N lines of a file safely."""
    try:
        p = Path(filepath)
        if p.exists() and p.stat().st_size < 1_000_000:
            return '\n'.join(p.read_text(errors='ignore').splitlines()[:lines])
    except Exception:
        pass
    return ''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--file',    help='Single file path to check')
    parser.add_argument('--snippet', default='', help='Content snippet for import checking')
    parser.add_argument('--scan',    action='store_true', help='Scan all staged/modified git files')
    parser.add_argument('--json',    action='store_true', dest='as_json', help='Output JSON')
    parser.add_argument('--no-color', action='store_true', help='Disable ANSI colors')
    args = parser.parse_args()

    wiki_dir  = Path(os.getcwd()) / 'wiki' / 'decisions'
    decisions = load_decisions(wiki_dir)

    if not decisions:
        if args.as_json:
            print(json.dumps({'violations': [], 'decisions_loaded': 0}))
        sys.exit(0)

    all_violations: list[dict] = []

    if args.scan:
        files = get_staged_files()
        for f in files:
            snippet = read_snippet(f)
            all_violations.extend(check_file(f, snippet, decisions))
    elif args.file:
        all_violations = check_file(args.file, args.snippet, decisions)

    if args.as_json:
        print(json.dumps({
            'violations':       all_violations,
            'decisions_loaded': len(decisions),
        }))
    else:
        out = format_violations(all_violations, color=not args.no_color)
        if out:
            print(out)


if __name__ == '__main__':
    main()
