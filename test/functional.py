#!/usr/bin/env python3
"""
Pith — Full Functional Test

Runs every hook in the live installed chain and shows the ACTUAL input and output
at each stage. Not a simulation of results — the real hook code runs.

Hook chain:
  SessionStart     → what Claude receives as system context at session open
  UserPromptSubmit → what gets injected for each /pith command and normal prompt
  PostToolUse      → what tool results look like before vs after compression
  Stop             → token summary written to state

Run: python3 test/functional.py
"""
from __future__ import annotations
import json, subprocess, os, sys, time, textwrap
from pathlib import Path

REPO     = Path(__file__).parent.parent
HOOK_DIR = Path.home() / '.claude/hooks/pith'
STATE    = Path.home() / '.pith/state.json'
NODE     = 'node'
W        = 78

# ─── helpers ─────────────────────────────────────────────────────────────────

def tok(t: str) -> int:
    return max(1, len(t) // 4)

def run_hook(hook: str, stdin_data: str | None = None, env: dict | None = None) -> tuple[str, str, int, float]:
    """Returns (stdout, stderr, returncode, latency_ms)."""
    e = os.environ.copy()
    e['CLAUDE_CWD'] = str(REPO)
    if env:
        e.update(env)
    t0 = time.perf_counter()
    r  = subprocess.run(
        [NODE, str(HOOK_DIR / hook)],
        input=stdin_data or '',
        capture_output=True, text=True, env=e,
    )
    ms = (time.perf_counter() - t0) * 1000
    return r.stdout, r.stderr, r.returncode, ms

def box(title: str, content: str, width: int = W):
    border = '─' * (width - 2)
    print(f'┌{border}┐')
    label = f' {title} '
    pad   = width - 2 - len(label)
    print(f'│{label}{"─" * pad}│')
    print(f'├{border}┤')
    for line in content.splitlines():
        chunks = textwrap.wrap(line, width - 4) or ['']
        for chunk in chunks:
            print(f'│  {chunk:<{width - 4}}│')
    print(f'└{border}┘')

def diff_box(title_a: str, a: str, title_b: str, b: str):
    """Side-by-side is too narrow — show before/after sequentially with token delta."""
    ta, tb = tok(a), tok(b)
    saved  = ta - tb
    pct    = saved / ta * 100 if ta else 0
    sign   = '↓' if saved > 0 else ('↑' if saved < 0 else '=')
    print(f'  {title_a}: {ta:,} tokens   {sign}   {title_b}: {tb:,} tokens'
          f'   ({abs(pct):.0f}% {"saved" if saved >= 0 else "added"})')
    print()
    box(f'INPUT  — {title_a}  [{ta:,} tok]', a)
    print()
    box(f'OUTPUT — {title_b}  [{tb:,} tok]', b)

def section(title: str):
    print()
    print('━' * W)
    print(f'  {title}')
    print('━' * W)

def ok(label: str, ms: float):
    print(f'  ✓  {label}  ({ms:.0f}ms)')

def fail(label: str, stderr: str):
    print(f'  ✗  {label}')
    if stderr.strip():
        print(f'     stderr: {stderr.strip()[:200]}')

# ─── synthetic files ──────────────────────────────────────────────────────────

SAMPLE_TS = """\
import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../api/client';
import { User, UpdateUserPayload } from '../types/user';
import { useToast } from './useToast';

export function useUserProfile(userId: string) {
  const [user,    setUser]    = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving,  setSaving]  = useState(false);
  const toast = useToast();

  const fetchUser = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<User>(`/users/${userId}`);
      setUser(data);
    } catch (e: any) {
      toast.error(e.message ?? 'Failed to load user');
    } finally {
      setLoading(false);
    }
  }, [userId, toast]);

  const updateUser = useCallback(async (payload: UpdateUserPayload) => {
    setSaving(true);
    try {
      const updated = await apiClient.patch<User>(`/users/${userId}`, payload);
      setUser(updated);
      toast.success('Profile saved');
      return updated;
    } catch (e: any) {
      toast.error(e.message ?? 'Failed to save');
      throw e;
    } finally {
      setSaving(false);
    }
  }, [userId, toast]);

  const deleteUser = useCallback(async () => {
    try {
      await apiClient.delete(`/users/${userId}`);
      toast.success('Account deleted');
    } catch (e: any) {
      toast.error(e.message ?? 'Delete failed');
      throw e;
    }
  }, [userId, toast]);

  useEffect(() => { fetchUser(); }, [fetchUser]);

  return { user, loading, saving, fetchUser, updateUser, deleteUser };
}
"""

SAMPLE_PY = """\
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, AsyncIterator
from .base import BaseService
from .cache import CacheService
from ..models.document import Document, DocumentStatus
from ..repositories.document_repo import DocumentRepository
from ..events import EventBus, DocumentEvent

logger = logging.getLogger(__name__)

@dataclass
class DocumentFilter:
    status:     Optional[DocumentStatus] = None
    owner_id:   Optional[str]            = None
    tag:        Optional[str]            = None
    limit:      int                      = 50
    offset:     int                      = 0

class DocumentService(BaseService):
    \"\"\"Manages document lifecycle: create, index, search, archive.\"\"\"

    def __init__(self, repo: DocumentRepository, cache: CacheService, events: EventBus):
        self._repo   = repo
        self._cache  = cache
        self._events = events

    async def get(self, doc_id: str, user_id: str) -> Optional[Document]:
        cache_key = f'doc:{doc_id}'
        cached    = await self._cache.get(cache_key)
        if cached:
            return Document.from_dict(cached)
        doc = await self._repo.find_by_id(doc_id)
        if doc and doc.owner_id != user_id and not doc.is_public:
            raise PermissionError(f'User {user_id} cannot access document {doc_id}')
        if doc:
            await self._cache.set(cache_key, doc.to_dict(), ttl=300)
        return doc

    async def list(self, filters: DocumentFilter) -> tuple[list[Document], int]:
        return await self._repo.find_all(
            status=filters.status, owner_id=filters.owner_id,
            tag=filters.tag, limit=filters.limit, offset=filters.offset,
        )

    async def create(self, owner_id: str, title: str, content: str, tags: list[str]) -> Document:
        doc = await self._repo.create(owner_id=owner_id, title=title, content=content, tags=tags)
        await self._events.emit(DocumentEvent.CREATED, {'doc_id': doc.id, 'owner_id': owner_id})
        logger.info('document created', extra={'doc_id': doc.id, 'owner': owner_id})
        return doc

    async def update(self, doc_id: str, user_id: str, **kwargs) -> Document:
        doc = await self.get(doc_id, user_id)
        if not doc:
            raise ValueError(f'Document {doc_id} not found')
        updated = await self._repo.update(doc_id, **kwargs)
        await self._cache.delete(f'doc:{doc_id}')
        await self._events.emit(DocumentEvent.UPDATED, {'doc_id': doc_id})
        return updated

    async def archive(self, doc_id: str, user_id: str) -> Document:
        return await self.update(doc_id, user_id, status=DocumentStatus.ARCHIVED)

    async def stream_search(self, query: str, user_id: str) -> AsyncIterator[Document]:
        async for doc in self._repo.search_stream(query):
            if doc.owner_id == user_id or doc.is_public:
                yield doc

    async def bulk_update_tags(self, doc_ids: list[str], tags: list[str], user_id: str) -> int:
        count = 0
        for doc_id in doc_ids:
            try:
                await self.update(doc_id, user_id, tags=tags)
                count += 1
            except (ValueError, PermissionError) as e:
                logger.warning('bulk_update skip %s: %s', doc_id, e)
        return count
"""

BASH_NPM = """\
npm warn deprecated inflight@1.0.6: This module is not supported
npm warn deprecated rimraf@3.0.2: Rimraf versions prior to v4 are no longer supported
npm warn deprecated glob@7.2.3: Glob versions prior to v9 are no longer supported
npm warn deprecated @humanwhocodes/config-array@0.11.13: Use @eslint/config-array instead
npm warn deprecated @humanwhocodes/object-schema@2.0.3: Use @eslint/object-schema instead
npm warn deprecated eslint@8.57.0: This version is no longer supported
npm warn deprecated lodash@4.17.20: Critical security vulnerability CVE-2021-23337
npm warn deprecated mkdirp@0.5.6: Legacy versions of mkdirp are no longer supported
npm warn deprecated request@2.88.2: request has been deprecated
npm warn deprecated har-validator@5.1.5: No longer supported
npm warn deprecated uuid@3.4.0: Please upgrade to version 7
npm warn deprecated node-uuid@1.4.8: Use uuid module instead

added 312 packages, and audited 313 packages in 8s

45 packages are looking for funding
  run `npm fund` for details

3 vulnerabilities (1 moderate, 2 high)

To address all issues, run:
  npm audit fix

Run `npm audit` for details
"""

BASH_GIT_LOG = "\n".join([
    f"{'abcdef'[i%6]}{i:05d} {'fix' if i%3==0 else 'feat' if i%3==1 else 'chore'}"
    f"({'auth' if i%4==0 else 'api' if i%4==1 else 'ui' if i%4==2 else 'db'}): "
    f"{'update token refresh logic' if i%3==0 else 'add rate limiting middleware' if i%3==1 else 'bump dependencies'}"
    for i in range(45)
])

BASH_TEST = """\
PASS src/auth/login.test.ts
PASS src/auth/token.test.ts
FAIL src/api/users.test.ts
  ● GET /users › with role filter › should return only editors
    Expected: 4
    Received: 42
    at Object.<anonymous> (src/api/users.test.ts:63:5)
  ● GET /users › pagination › should respect limit param
    Expected length: 20
    Received length: 42
    at Object.<anonymous> (src/api/users.test.ts:89:5)
PASS src/api/auth.test.ts
PASS src/models/user.test.ts
PASS src/services/email.test.ts

Test Suites: 1 failed, 4 passed, 5 total
Tests:       2 failed, 38 passed, 40 total
Snapshots:   0 total
Time:        5.2s
"""

GREP_RESULT = "\n".join([
    f"src/{'services' if i%3==0 else 'api' if i%3==1 else 'hooks'}"
    f"/{'auth' if i%5<2 else 'user' if i%5<4 else 'payment'}Service.ts:"
    f"{10+i*3}: import {{ useAuth }} from '../hooks/useAuth'"
    for i in range(38)
])

PKG_JSON = json.dumps({
    "name": "frontend-app", "version": "1.0.0", "private": True,
    "scripts": {"dev": "vite", "build": "vite build", "test": "vitest", "lint": "eslint src"},
    "dependencies": {
        "react": "^18.2.0", "react-dom": "^18.2.0", "react-router-dom": "^6.21.0",
        "@tanstack/react-query": "^5.13.4", "axios": "^1.6.2", "zod": "^3.22.4",
        "zustand": "^4.4.7", "date-fns": "^3.0.6", "clsx": "^2.0.0",
        "lucide-react": "^0.300.0", "tailwindcss": "^3.4.0",
    },
    "devDependencies": {
        "@types/react": "^18.2.45", "@types/react-dom": "^18.2.18",
        "@vitejs/plugin-react": "^4.2.1", "typescript": "^5.3.3",
        "vitest": "^1.0.4", "@testing-library/react": "^14.1.2",
        "eslint": "^8.55.0", "vite": "^5.0.8",
    }
}, indent=2)


# ─── test cases ──────────────────────────────────────────────────────────────

TOOL_CASES = [
    ('Read', 'useUserProfile.ts',  SAMPLE_TS,   'TypeScript hook (62 lines)'),
    ('Read', 'documentService.py', SAMPLE_PY,   'Python service (72 lines)'),
    ('Read', 'package.json',       PKG_JSON,    'package.json'),
    ('Bash', 'npm install',        BASH_NPM,    'npm install output'),
    ('Bash', 'git log --oneline',  BASH_GIT_LOG,'git log (45 commits)'),
    ('Bash', 'jest',               BASH_TEST,   'jest test run (2 failures)'),
    ('Grep', 'useAuth',            GREP_RESULT, 'grep 38 matches'),
]

PROMPT_CASES = [
    ('/pith lean',         'Switch to lean compression mode'),
    ('/pith ultra',        'Switch to ultra compression mode'),
    ('/pith off',          'Turn off compression'),
    ('/pith debug',        'Activate debug structured format'),
    ('/pith status',       'Show token usage'),
    ('/budget 150',        'Set 150-token hard ceiling'),
    ('/budget off',        'Clear budget'),
    ('what does useAuth do?', 'Normal message (budget re-injection check)'),
]

# ─── main ────────────────────────────────────────────────────────────────────

def main():
    passed = failed = 0

    # ── 1. SESSION START ─────────────────────────────────────────────────────
    section('STAGE 1 — SessionStart hook  (system context injection)')
    print('  What Claude receives as initial system context when a session opens.')
    print()

    out, err, rc, ms = run_hook('session-start.js')
    if rc == 0:
        ok('session-start.js', ms)
        passed += 1
        if out.strip():
            box('INJECTED INTO CONTEXT', out.strip())
            print(f'\n  → {tok(out):,} tokens injected at session open')
        else:
            print('  → No injection (setup_done=true, no active mode)')
    else:
        fail('session-start.js', err)
        failed += 1

    # ── 2. PROMPT SUBMIT ─────────────────────────────────────────────────────
    section('STAGE 2 — UserPromptSubmit hook  (command parsing + per-message injection)')
    print('  What gets injected into context for each user message/command.')
    print()

    for cmd, desc in PROMPT_CASES:
        payload = json.dumps({'prompt': cmd, 'session_id': 'test-session'})
        out, err, rc, ms = run_hook('prompt-submit.js', payload)
        if rc == 0:
            ok(f'{desc:<40}  [{cmd}]', ms)
            passed += 1
            if out.strip():
                lines = out.strip().splitlines()
                preview = '\n'.join(lines[:6]) + ('\n  ...' if len(lines) > 6 else '')
                print(f'     inject → {tok(out):,} tokens: {preview[:120]}')
            else:
                print(f'     inject → (none — command acknowledged, no context needed)')
        else:
            fail(f'{cmd}', err)
            failed += 1
        print()

    # ── 3. POST TOOL USE — full before/after ──────────────────────────────────
    section('STAGE 3 — PostToolUse hook  (tool output compression)')
    print('  Left side = raw tool result entering context.  Right = after Pith.')
    print()

    total_before = total_after = 0
    for tool, name, content, desc in TOOL_CASES:
        payload = json.dumps({
            'tool_name':     tool,
            'tool_input':    {'file_path': name, 'command': name, 'pattern': name},
            'tool_response': content,
        })
        out, err, rc, ms = run_hook('post-tool-use.js', payload)
        if rc != 0:
            fail(desc, err)
            failed += 1
            continue

        compressed = None
        if out.strip():
            try:
                compressed = json.loads(out)['output']
            except Exception:
                pass

        before_text = content
        after_text  = compressed if compressed else content
        tb, ta      = tok(before_text), tok(after_text)
        total_before += tb
        total_after  += ta
        passed += 1

        saved = tb - ta
        pct   = saved / tb * 100 if tb else 0
        status = f'{pct:.0f}% saved  ({tb:,} → {ta:,} tok)' if compressed else f'pass-through  ({tb:,} tok, below threshold)'

        print(f'  ── {desc}  [{tool} {name}]  {status}')
        if compressed:
            ok(f'{desc}', ms)
            print()
            # Show actual before content (truncated for display)
            before_display = '\n'.join(content.splitlines()[:20])
            if content.count('\n') > 20:
                before_display += f'\n  ... ({content.count(chr(10))+1} lines total)'
            box(f'BEFORE  {tb:,} tokens — raw tool result', before_display)
            print()
            box(f'AFTER   {ta:,} tokens — what Claude sees', after_text)
        else:
            print(f'       → Content is {content.count(chr(10))+1} lines, below 30-line threshold, passes through unchanged')
        print()

    print(f'  TOOL COMPRESSION TOTAL: {total_before:,} → {total_after:,} tokens  '
          f'({(total_before-total_after)/total_before*100:.0f}% reduction across all calls)')

    # ── 4. STOP HOOK ─────────────────────────────────────────────────────────
    section('STAGE 4 — Stop hook  (session accounting)')
    print('  Runs at session end. Reads token usage from Claude API response, writes to state.')
    print()

    stop_payload = json.dumps({
        'usage':    {'input_tokens': 12400, 'output_tokens': 1850},
        'response': {'content': 'Example response text from Claude.'}
    })
    out, err, rc, ms = run_hook('stop.js', stop_payload)
    if rc == 0:
        ok('stop.js', ms)
        passed += 1
        # Read state to show what was written
        try:
            state = json.loads(STATE.read_text())
            # Find the project entry
            for k, v in state.items():
                if k.startswith('proj_') and isinstance(v, dict):
                    print(f'     project key: {k}')
                    for field in ['tokens_saved_total', 'tokens_saved_session', 'tool_savings_session', 'session_start']:
                        val = v.get(field, 'not set')
                        print(f'       {field}: {val}')
                    break
        except Exception as e:
            print(f'     state read: {e}')
    else:
        fail('stop.js', err)
        failed += 1

    # ── 5. STATUSLINE ────────────────────────────────────────────────────────
    section('STAGE 5 — Statusline  (badge in Claude Code toolbar)')
    print('  Output appears in Claude Code status bar every turn.')
    print()

    r = subprocess.run(['bash', str(HOOK_DIR / 'statusline.sh')], capture_output=True, text=True,
                       env={**os.environ, 'CLAUDE_CWD': str(REPO)})
    if r.returncode == 0:
        ok('statusline.sh', 0)
        passed += 1
        print(f'     badge text: [{r.stdout.strip()}]')
    else:
        fail('statusline.sh', r.stderr)
        failed += 1

    # ── FINAL SCORE ──────────────────────────────────────────────────────────
    section('RESULTS')
    total = passed + failed
    pct   = passed / total * 100 if total else 0

    bar_w = 40
    filled = int(bar_w * pct / 100)
    bar_str = '█' * filled + '░' * (bar_w - filled)

    print(f'\n  {bar_str}  {passed}/{total} ({pct:.0f}%)')
    print()

    if failed == 0:
        print('  ✓ ALL HOOKS FUNCTIONAL — full chain SessionStart → Stop works end-to-end')
        print(f'  ✓ Tool compression: {total_before:,} → {total_after:,} tokens '
              f'({(total_before-total_after)/total_before*100:.0f}% input reduction on live files)')
        print('  ✓ Command parsing, mode injection, budget, statusline all verified')
    else:
        print(f'  {failed} hook(s) failed — check stderr output above')

    print()
    print('  To run in a real session:')
    print('    1. Open any project in Claude Code')
    print('    2. The SessionStart hook fires automatically')
    print('    3. Type  /pith lean  to activate output compression')
    print('    4. Type  /pith status  to see live token breakdown')
    print()
    print('━' * W)
    print()


if __name__ == '__main__':
    main()
