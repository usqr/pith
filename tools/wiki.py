#!/usr/bin/env python3
"""
Pith Wiki Query — find and return relevant wiki pages for a question.
Uses index.md to find relevant pages, then focus.py to extract relevant sections.

Usage:
    python3 wiki.py --question "why did we choose postgres?"
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

# Reuse focus logic inline (avoid import path issues)
STOP_WORDS = {
    'the','a','an','is','are','was','were','be','have','do','how','what',
    'where','when','why','who','which','that','this','to','of','in','for',
    'on','with','at','by','from','and','but','or','not','if','about',
}


def keywords(text: str) -> set[str]:
    words = re.findall(r'[a-zA-Z][a-zA-Z0-9]*', text.lower())
    return {w for w in words if w not in STOP_WORDS and len(w) > 2}


def score_page(text: str, kws: set[str]) -> float:
    if not kws: return 0.0
    low = text.lower()
    hits = sum(1 + min(low.count(kw) - 1, 2) * 0.3 for kw in kws if low.count(kw) > 0)
    return hits / (1 + len(low.split()) / 200)


def find_wiki(cwd: Path) -> Path | None:
    for candidate in [cwd / 'wiki', cwd / 'docs' / 'wiki', cwd / '.wiki']:
        if candidate.is_dir():
            return candidate
    return None


def parse_index(index_path: Path) -> list[tuple[str, Path]]:
    """Parse index.md to get (page_name, page_path) pairs."""
    if not index_path.exists():
        return []
    content = index_path.read_text(errors='ignore')
    entries = []
    for line in content.split('\n'):
        # Match: - [[Name]](path/to/file.md) — description
        m = re.match(r'\s*-\s+\[\[([^\]]+)\]\]\(([^)]+)\)', line)
        if m:
            name      = m.group(1)
            rel_path  = m.group(2)
            page_path = index_path.parent / rel_path
            entries.append((name, page_path))
    return entries


def query(question: str, top_k: int = 4) -> str:
    cwd  = Path.cwd()
    wiki = find_wiki(cwd)

    if not wiki:
        return '[PITH WIKI: no wiki directory found. Run /pith setup to create one.]'

    index_path = wiki / 'index.md'
    if not index_path.exists():
        # Fall back to listing all .md files in wiki
        pages = list(wiki.rglob('*.md'))
    else:
        page_entries = parse_index(index_path)
        pages = [p for _, p in page_entries if p.exists()]

    if not pages:
        return '[PITH WIKI: wiki is empty. Use /pith ingest <file> to add sources.]'

    kws = keywords(question)

    # Score each page
    scored = []
    for page_path in pages:
        if not page_path.exists(): continue
        content = page_path.read_text(errors='ignore')
        s = score_page(content, kws)
        # Boost decisions pages for "why" questions
        if 'why' in question.lower() and 'decisions' in str(page_path): s *= 1.5
        scored.append((s, page_path, content))

    scored.sort(key=lambda x: -x[0])
    top = [x for x in scored[:top_k] if x[0] > 0]

    if not top:
        return f'[PITH WIKI: no relevant pages found for "{question[:60]}". Wiki has {len(pages)} pages total.]'

    parts = [f'[PITH WIKI: {len(pages)} pages total, {len(top)} relevant to: "{question[:80]}"]\n']
    for _, page_path, content in top:
        rel = page_path.relative_to(cwd) if page_path.is_relative_to(cwd) else page_path
        lines = content.split('\n')
        # Show first 40 lines of each relevant page
        preview = '\n'.join(lines[:40])
        if len(lines) > 40:
            preview += f'\n[...{len(lines) - 40} more lines — ask for full page: {rel}]'
        parts.append(f'--- {rel} ---\n{preview}')

    return '\n\n'.join(parts)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--question', '-q', default='')
    p.add_argument('--top', '-k', type=int, default=4)
    args = p.parse_args()
    print(query(args.question or ' '.join(sys.argv[1:]), args.top))

if __name__ == '__main__':
    main()
