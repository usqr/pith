#!/usr/bin/env python3
"""
Pith — End-to-End Session Simulator

Simulates three realistic Claude Code sessions with synthetic but accurate file contents.
Runs every hook in sequence (SessionStart → UserPromptSubmit → PostToolUse × N → Stop)
against a no-pith baseline and scores the result across five dimensions.

No API key needed. All compression is the actual hook code, not mocked.

Run: python3 test/simulator.py
"""
from __future__ import annotations
import json, subprocess, time, sys, textwrap
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

REPO     = Path(__file__).parent.parent
HOOK_DIR = Path.home() / '.claude/hooks/pith'
if not HOOK_DIR.exists():
    HOOK_DIR = REPO / 'hooks'

NODE     = 'node'

# ─────────────────────────────────────────────────────────────────────────────
# Synthetic but realistic file contents for three coding scenarios
# ─────────────────────────────────────────────────────────────────────────────

FILES = {}

FILES['src/auth/useAuth.ts'] = """\
import { useState, useEffect, useCallback, useContext } from 'react';
import { AuthContext } from './AuthContext';
import { authService } from '../services/authService';
import { User, AuthState, LoginPayload } from '../types/auth';
import { logger } from '../utils/logger';
import { tokenStorage } from '../utils/tokenStorage';

const REFRESH_INTERVAL_MS = 4 * 60 * 1000; // 4 minutes

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}

export function useAuthProvider(): AuthState {
  const [user, setUser]       = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  const login = useCallback(async (payload: LoginPayload) => {
    setLoading(true);
    setError(null);
    try {
      const { user, accessToken, refreshToken } = await authService.login(payload);
      tokenStorage.set('access',  accessToken);
      tokenStorage.set('refresh', refreshToken);
      setUser(user);
      logger.info('login success', { userId: user.id });
    } catch (e: any) {
      const msg = e.response?.data?.message ?? 'Login failed';
      setError(msg);
      logger.error('login failed', { error: msg });
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } finally {
      tokenStorage.clear();
      setUser(null);
      logger.info('logged out');
    }
  }, []);

  const refreshToken = useCallback(async () => {
    const rt = tokenStorage.get('refresh');
    if (!rt) { setUser(null); return; }
    try {
      const { accessToken } = await authService.refresh(rt);
      tokenStorage.set('access', accessToken);
    } catch {
      tokenStorage.clear();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    const init = async () => {
      const access = tokenStorage.get('access');
      if (!access) { setLoading(false); return; }
      try {
        const user = await authService.me(access);
        setUser(user);
      } catch {
        await refreshToken();
      } finally {
        setLoading(false);
      }
    };
    init();
  }, [refreshToken]);

  useEffect(() => {
    if (!user) return;
    const id = setInterval(refreshToken, REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [user, refreshToken]);

  return { user, loading, error, login, logout, refreshToken };
}
"""

FILES['src/services/authService.ts'] = """\
import axios from 'axios';
import { LoginPayload, AuthResponse, RefreshResponse, User } from '../types/auth';

const BASE = process.env.REACT_APP_API_URL ?? 'http://localhost:4000';
const api   = axios.create({ baseURL: BASE, withCredentials: true });

api.interceptors.response.use(
  r => r,
  async err => {
    const orig = err.config;
    if (err.response?.status === 401 && !orig._retry) {
      orig._retry = true;
      try {
        const rt = localStorage.getItem('refresh_token');
        if (!rt) throw new Error('no refresh token');
        const { data } = await api.post<RefreshResponse>('/auth/refresh', { refreshToken: rt });
        localStorage.setItem('access_token', data.accessToken);
        orig.headers['Authorization'] = `Bearer ${data.accessToken}`;
        return api(orig);
      } catch {
        localStorage.clear();
        window.location.href = '/login';
      }
    }
    return Promise.reject(err);
  }
);

export const authService = {
  async login(payload: LoginPayload): Promise<AuthResponse> {
    const { data } = await api.post<AuthResponse>('/auth/login', payload);
    return data;
  },

  async logout(): Promise<void> {
    await api.post('/auth/logout');
  },

  async refresh(refreshToken: string): Promise<RefreshResponse> {
    const { data } = await api.post<RefreshResponse>('/auth/refresh', { refreshToken });
    return data;
  },

  async me(accessToken: string): Promise<User> {
    const { data } = await api.get<User>('/auth/me', {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return data;
  },

  async forgotPassword(email: string): Promise<void> {
    await api.post('/auth/forgot-password', { email });
  },

  async resetPassword(token: string, password: string): Promise<void> {
    await api.post('/auth/reset-password', { token, password });
  },
};
"""

FILES['src/api/userController.ts'] = """\
import { Request, Response, NextFunction } from 'express';
import { userService } from '../services/userService';
import { validateCreateUser, validateUpdateUser } from '../validators/userValidator';
import { paginate } from '../utils/pagination';
import { cache } from '../utils/cache';
import { logger } from '../utils/logger';
import { AppError } from '../errors/AppError';
import { UserRole } from '../models/User';

const USER_CACHE_TTL = 300; // 5 minutes

export class UserController {
  async list(req: Request, res: Response, next: NextFunction) {
    try {
      const { page = 1, limit = 20, role, search, sortBy = 'createdAt', order = 'desc' } = req.query;
      const cacheKey = `users:list:${JSON.stringify(req.query)}`;
      const cached   = await cache.get(cacheKey);
      if (cached) return res.json(cached);

      const { users, total } = await userService.findAll({
        page: Number(page), limit: Number(limit),
        role: role as UserRole, search: search as string,
        sortBy: sortBy as string, order: order as 'asc' | 'desc',
      });
      const result = paginate(users, total, Number(page), Number(limit));
      await cache.set(cacheKey, result, USER_CACHE_TTL);
      logger.info('users listed', { count: users.length, userId: req.user?.id });
      res.json(result);
    } catch (e) { next(e); }
  }

  async getById(req: Request, res: Response, next: NextFunction) {
    try {
      const { id } = req.params;
      const cacheKey = `users:${id}`;
      const cached   = await cache.get(cacheKey);
      if (cached) return res.json(cached);

      const user = await userService.findById(id);
      if (!user) throw new AppError('User not found', 404);
      await cache.set(cacheKey, user, USER_CACHE_TTL);
      res.json(user);
    } catch (e) { next(e); }
  }

  async create(req: Request, res: Response, next: NextFunction) {
    try {
      const { error, value } = validateCreateUser(req.body);
      if (error) throw new AppError(error.message, 400);
      const user = await userService.create(value);
      logger.info('user created', { userId: user.id, by: req.user?.id });
      res.status(201).json(user);
    } catch (e) { next(e); }
  }

  async update(req: Request, res: Response, next: NextFunction) {
    try {
      const { id } = req.params;
      const { error, value } = validateUpdateUser(req.body);
      if (error) throw new AppError(error.message, 400);
      const user = await userService.update(id, value);
      if (!user) throw new AppError('User not found', 404);
      await cache.invalidate(`users:${id}`);
      logger.info('user updated', { userId: id, by: req.user?.id });
      res.json(user);
    } catch (e) { next(e); }
  }

  async delete(req: Request, res: Response, next: NextFunction) {
    try {
      const { id } = req.params;
      if (id === req.user?.id) throw new AppError('Cannot delete yourself', 400);
      await userService.delete(id);
      await cache.invalidate(`users:${id}`);
      logger.info('user deleted', { userId: id, by: req.user?.id });
      res.status(204).send();
    } catch (e) { next(e); }
  }
}
"""

FILES['src/models/user.py'] = """\
from __future__ import annotations
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Boolean, DateTime, Enum as SAEnum, ForeignKey, Index
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from passlib.context import CryptContext
from .base import Base

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

class UserRole(enum.Enum):
    ADMIN   = 'admin'
    EDITOR  = 'editor'
    VIEWER  = 'viewer'

class UserStatus(enum.Enum):
    ACTIVE   = 'active'
    INACTIVE = 'inactive'
    BANNED   = 'banned'

class User(Base):
    \"\"\"Core user model. Passwords stored as bcrypt hashes. Never expose hash in API.\"\"\"
    __tablename__ = 'users'
    __table_args__ = (
        Index('ix_users_email',      'email',      unique=True),
        Index('ix_users_username',   'username',   unique=True),
        Index('ix_users_created_at', 'created_at'),
    )

    id          = Column(String(36),  primary_key=True)
    email       = Column(String(255), nullable=False)
    username    = Column(String(64),  nullable=False)
    _password   = Column('password_hash', String(128), nullable=False)
    first_name  = Column(String(64),  nullable=True)
    last_name   = Column(String(64),  nullable=True)
    role        = Column(SAEnum(UserRole),   nullable=False, default=UserRole.VIEWER)
    status      = Column(SAEnum(UserStatus), nullable=False, default=UserStatus.ACTIVE)
    is_verified = Column(Boolean, nullable=False, default=False)
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at  = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login  = Column(DateTime, nullable=True)

    sessions    = relationship('Session',      back_populates='user', cascade='all, delete-orphan')
    audit_logs  = relationship('AuditLog',     back_populates='user', lazy='dynamic')
    permissions = relationship('Permission',   back_populates='user', cascade='all, delete-orphan')

    @hybrid_property
    def password(self):
        raise AttributeError('password is write-only')

    @password.setter
    def password(self, plain: str):
        if len(plain) < 8:
            raise ValueError('Password must be at least 8 characters')
        self._password = pwd_context.hash(plain)

    def verify_password(self, plain: str) -> bool:
        return pwd_context.verify(plain, self._password)

    @hybrid_property
    def full_name(self) -> str:
        parts = filter(None, [self.first_name, self.last_name])
        return ' '.join(parts) or self.username

    @validates('email')
    def validate_email(self, key, value):
        if '@' not in value:
            raise ValueError(f'Invalid email: {value}')
        return value.lower().strip()

    @validates('role')
    def validate_role(self, key, value):
        if isinstance(value, str):
            return UserRole(value)
        return value

    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    def to_dict(self, include_sensitive: bool = False) -> dict:
        d = {
            'id': self.id, 'email': self.email, 'username': self.username,
            'first_name': self.first_name, 'last_name': self.last_name,
            'full_name': self.full_name, 'role': self.role.value,
            'status': self.status.value, 'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat(), 'last_login': self.last_login.isoformat() if self.last_login else None,
        }
        return d

    def __repr__(self) -> str:
        return f'<User {self.username} ({self.role.value})>'
"""

FILES['src/pipeline/processor.py'] = """\
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable, Optional, Any
from collections import defaultdict
from .stages import Stage, StageResult, StageStatus
from .context import PipelineContext
from .metrics import PipelineMetrics
from .errors import PipelineError, StageError

logger = logging.getLogger(__name__)

@dataclass
class PipelineConfig:
    max_concurrency: int = 4
    timeout_seconds: float = 300.0
    retry_attempts:  int   = 3
    retry_delay:     float = 1.0
    fail_fast:       bool  = False

@dataclass
class PipelineResult:
    success:  bool
    stages:   list[StageResult]
    duration: float
    errors:   list[str] = field(default_factory=list)

class Pipeline:
    \"\"\"Async multi-stage processing pipeline with concurrency control and retries.\"\"\"

    def __init__(self, name: str, config: Optional[PipelineConfig] = None):
        self.name    = name
        self.config  = config or PipelineConfig()
        self._stages: list[Stage]      = []
        self._hooks:  dict[str, list[Callable]] = defaultdict(list)
        self._metrics = PipelineMetrics(name)

    def add_stage(self, stage: Stage) -> 'Pipeline':
        self._stages.append(stage)
        return self

    def on(self, event: str, handler: Callable) -> 'Pipeline':
        self._hooks[event].append(handler)
        return self

    async def run(self, context: PipelineContext) -> PipelineResult:
        start = asyncio.get_event_loop().time()
        results: list[StageResult] = []
        errors:  list[str]         = []

        await self._fire('pipeline.start', context)
        sem = asyncio.Semaphore(self.config.max_concurrency)

        try:
            for stage in self._stages:
                result = await self._run_stage(stage, context, sem)
                results.append(result)
                if result.status == StageStatus.FAILED:
                    errors.append(f'{stage.name}: {result.error}')
                    if self.config.fail_fast:
                        break
        except asyncio.TimeoutError:
            errors.append('Pipeline timed out')
        except Exception as e:
            errors.append(str(e))
            logger.exception('Pipeline %s failed', self.name)

        duration = asyncio.get_event_loop().time() - start
        success  = len(errors) == 0
        self._metrics.record(success, duration)
        await self._fire('pipeline.end', context, success=success)

        return PipelineResult(success=success, stages=results, duration=duration, errors=errors)

    async def _run_stage(self, stage: Stage, ctx: PipelineContext, sem: asyncio.Semaphore) -> StageResult:
        for attempt in range(1, self.config.retry_attempts + 1):
            async with sem:
                try:
                    await self._fire(f'stage.start', ctx, stage=stage.name)
                    result = await asyncio.wait_for(
                        stage.execute(ctx),
                        timeout=self.config.timeout_seconds,
                    )
                    await self._fire('stage.end', ctx, stage=stage.name, result=result)
                    return result
                except StageError as e:
                    if attempt == self.config.retry_attempts:
                        logger.error('Stage %s failed after %d attempts: %s', stage.name, attempt, e)
                        return StageResult(stage=stage.name, status=StageStatus.FAILED, error=str(e))
                    await asyncio.sleep(self.config.retry_delay * attempt)

    async def _fire(self, event: str, *args, **kwargs) -> None:
        for handler in self._hooks.get(event, []):
            try:
                await asyncio.ensure_future(handler(*args, **kwargs)) if asyncio.iscoroutinefunction(handler) else handler(*args, **kwargs)
            except Exception:
                logger.exception('Hook %s failed for event %s', handler.__name__, event)

    def stream(self, context: PipelineContext) -> AsyncIterator[StageResult]:
        return self._stream_impl(context)

    async def _stream_impl(self, context: PipelineContext) -> AsyncIterator[StageResult]:
        sem = asyncio.Semaphore(self.config.max_concurrency)
        for stage in self._stages:
            result = await self._run_stage(stage, context, sem)
            yield result
            if result.status == StageStatus.FAILED and self.config.fail_fast:
                return
"""

FILES['package.json'] = """\
{
  "name": "myapp-backend",
  "version": "2.4.1",
  "type": "module",
  "main": "dist/index.js",
  "scripts": {
    "dev":        "tsx watch src/index.ts",
    "build":      "tsc --project tsconfig.build.json",
    "start":      "node dist/index.js",
    "test":       "jest --coverage",
    "test:watch": "jest --watch",
    "lint":       "eslint src --ext .ts",
    "typecheck":  "tsc --noEmit",
    "db:migrate": "prisma migrate deploy",
    "db:seed":    "tsx src/scripts/seed.ts",
    "docker:up":  "docker-compose up -d"
  },
  "dependencies": {
    "@prisma/client": "^5.7.0",
    "axios": "^1.6.2",
    "bcryptjs": "^2.4.3",
    "compression": "^1.7.4",
    "cors": "^2.8.5",
    "dotenv": "^16.3.1",
    "express": "^4.18.2",
    "express-rate-limit": "^7.1.5",
    "helmet": "^7.1.0",
    "ioredis": "^5.3.2",
    "jsonwebtoken": "^9.0.2",
    "morgan": "^1.10.0",
    "pg": "^8.11.3",
    "pino": "^8.16.2",
    "uuid": "^9.0.1",
    "zod": "^3.22.4"
  },
  "devDependencies": {
    "@types/bcryptjs": "^2.4.6",
    "@types/compression": "^1.7.5",
    "@types/cors": "^2.8.17",
    "@types/express": "^4.17.21",
    "@types/jest": "^29.5.10",
    "@types/jsonwebtoken": "^9.0.5",
    "@types/morgan": "^1.9.9",
    "@types/node": "^20.10.4",
    "@types/pg": "^8.10.9",
    "@types/uuid": "^9.0.7",
    "@typescript-eslint/eslint-plugin": "^6.14.0",
    "@typescript-eslint/parser": "^6.14.0",
    "eslint": "^8.55.0",
    "jest": "^29.7.0",
    "prisma": "^5.7.0",
    "ts-jest": "^29.1.1",
    "tsx": "^4.6.2",
    "typescript": "^5.3.3"
  }
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# Session definitions: each turn has tool calls (Read/Bash/Grep) + a response
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ToolCall:
    tool: str
    name: str
    content: str   # what the tool returned

@dataclass
class Turn:
    user_msg:   str
    tool_calls: list[ToolCall]
    response:   str            # what Claude would say without pith
    response_lean: str         # what Claude would say with /pith lean

SESSIONS: dict[str, list[Turn]] = {}

SESSIONS['react_auth_debug'] = [
    Turn(
        user_msg="The login redirect is broken — after login it always goes to /home instead of the previous page",
        tool_calls=[
            ToolCall('Read', 'useAuth.ts',     FILES['src/auth/useAuth.ts']),
            ToolCall('Read', 'authService.ts', FILES['src/services/authService.ts']),
        ],
        response="""\
I can see the issue. Looking at `useAuth.ts`, the `login` function in `useAuthProvider` doesn't
have any logic to redirect to a previous URL — it just calls `authService.login()` and sets the user.
The redirect behavior would need to be implemented in the component that calls `login()`, typically by
reading a `redirect` query parameter or storing the intended destination before redirecting to /login.

Here's what's happening:
1. User tries to access a protected route
2. They get redirected to /login (presumably by a PrivateRoute component)
3. After login, `setUser(user)` triggers a re-render
4. Whatever component is watching `user` (probably App.tsx or a router guard) redirects to /home as
   the default fallback since there's no "return to" logic

To fix this, you need to:
1. Store the intended URL before redirecting to login (e.g., `location.state = { from: currentPath }`)
2. In your login success handler in the component (not the hook), read that stored path
3. Navigate to the stored path, falling back to /home if none exists

The `authService.ts` file looks fine — it handles 401 refresh correctly and the logout redirect
at line 26 is a separate concern.
""",
        response_lean="""\
`login()` in `useAuth.ts` calls service + sets user — no redirect logic. Redirect happens wherever
`user` state change is observed (App.tsx/router guard), defaults to /home since no return-URL stored.

Fix:
1. Before redirecting to /login, store intended path: `state: { from: location.pathname }`
2. In login component's success handler, read `location.state?.from` and navigate there
3. Fallback to /home if undefined

`authService.ts` is fine — 401 interceptor and logout redirect are unrelated.
""",
    ),
    Turn(
        user_msg="Now run the auth tests and show me what's failing",
        tool_calls=[
            ToolCall('Bash', 'jest src/auth', '\n'.join(
                [f'PASS src/auth/authService.test.ts'] +
                ['FAIL src/auth/useAuth.test.ts',
                 '  ● useAuth › login › should redirect to previous page after login',
                 '    Expected navigate to have been called with "/dashboard"',
                 '    Received: navigate("/home")',
                 '    at Object.<anonymous> (src/auth/useAuth.test.ts:87:5)',
                 '  ● useAuth › login › should store redirect path in location state',
                 '    TypeError: Cannot read properties of undefined (reading "from")',
                 '    at useAuthProvider (src/auth/useAuth.ts:31:28)',
                 ''] +
                [f'PASS src/auth/tokenStorage.test.ts'] * 1 +
                ['', 'Tests: 2 failed, 18 passed, 20 total', 'Time: 3.4s']
            )),
        ],
        response="""\
The tests confirm exactly what we diagnosed. Two failures in `useAuth.test.ts`:

1. **Redirect test** (`L87`): The test expects `navigate("/dashboard")` after login but gets
   `navigate("/home")`. This test was written anticipating the redirect feature — it's testing the
   behavior we need to add.

2. **Location state test** (`L31`): `TypeError: Cannot read properties of undefined (reading "from")`.
   The hook is trying to read `location.state.from` but `location.state` is undefined. This means
   either the mock in the test doesn't set up `location.state`, or the real code is reading it
   without a null check.

Both failures are in the same area of `useAuth.ts` around line 31. The fix we discussed will
resolve both — once you add the `location.state?.from` read with proper optional chaining,
the TypeError goes away, and once the navigation calls the right path, the redirect test passes.
""",
        response_lean="""\
2 failures confirm the diagnosis.

`useAuth.test.ts:87` — expects `navigate("/dashboard")`, gets `navigate("/home")` — redirect feature missing.
`useAuth.ts:31` — `TypeError: location.state?.from` read without null check (or test doesn't set up state).

Both fixed by same change: add `location.state?.from` read in login success handler + optional chaining.
""",
    ),
    Turn(
        user_msg="What's the package.json look like — check deps",
        tool_calls=[
            ToolCall('Read', 'package.json', FILES['package.json']),
        ],
        response="""\
I can see the full package.json. For the auth redirect fix, the relevant dependencies are already there:
- `react-router-dom` would be in the frontend package (this appears to be the backend package.json)
- The backend has `jsonwebtoken@9.0.2` for JWT handling and `express@4.18.2`

Actually, looking at this more carefully, this is the **backend** `package.json`. The auth hook
(`useAuth.ts`) is a React hook that would live in a separate frontend package. You'd want to check
the frontend's `package.json` for `react-router-dom` to confirm the `useNavigate` and `useLocation`
hooks are available.

The backend dependencies look solid — `ioredis`, `pg`, `prisma`, `zod` all present. The security
headers with `helmet` are there. Dependency versions all look current.
""",
        response_lean="""\
This is the backend package.json — `useAuth.ts` is frontend, check frontend package for `react-router-dom`.

Backend deps: jsonwebtoken@9, express@4.18, helmet, ioredis, prisma — all current. No issues.
""",
    ),
]

SESSIONS['node_api_slowdown'] = [
    Turn(
        user_msg="The /users endpoint is taking 2-3 seconds. Profile it.",
        tool_calls=[
            ToolCall('Read', 'userController.ts', FILES['src/api/userController.ts']),
            ToolCall('Bash', 'grep -r "findAll"', '\n'.join(
                [f'src/services/userService.ts:{10+i*4}: async findAll(opts) {{ return db.query(...)' for i in range(8)] +
                [f'src/repositories/userRepository.ts:{5+i*3}: findAll: async (filters) => {{' for i in range(6)]
            )),
        ],
        response="""\
Looking at `userController.ts`, I can see several potential causes for the 2-3 second latency.

The `list` endpoint (lines 9-23) does the following on every request:
1. Builds a cache key from `req.query` (fine)
2. Checks Redis cache — if hit, returns immediately (fast path)
3. On cache miss: calls `userService.findAll()` with pagination/filtering params
4. Stores result in cache with 5-minute TTL

The slow path is step 3. From the grep results, `findAll` is called in both `userService.ts` and
`userRepository.ts` — there may be an N+1 pattern if the service calls the repository multiple
times (once for the filtered list, once for the total count separately).

Also notice: the cache key is built from the full `req.query` object including pagination. This means
page=1 and page=2 are cached separately, which is correct, but also means the cache has very low hit
rate for a paginated API if users aren't hitting the same exact page/sort combination.

To diagnose precisely: add `EXPLAIN ANALYZE` on the underlying SQL query and check if there's
a missing index on the columns used in `search`, `role`, or `sortBy`. The `users` table likely
needs a composite index on `(role, created_at)` and a GIN/trgm index for the `search` field.
""",
        response_lean="""\
`list()` in `userController.ts`: cache key includes full `req.query` → low hit rate for paginated queries.
On cache miss, hits `userService.findAll()`.

Likely causes:
1. N+1 in `userService` — separate queries for list + count (seen in grep: 8 `findAll` call sites)
2. Missing index on `role`, `created_at`, or `search` columns
3. `search` param doing `ILIKE %term%` with no trgm index → seq scan

Next: `EXPLAIN ANALYZE` on the query + check `userRepository.ts` for count query pattern.
""",
    ),
    Turn(
        user_msg="Run EXPLAIN on a sample query and check migration history",
        tool_calls=[
            ToolCall('Bash', 'psql -c "EXPLAIN ANALYZE..."', '\n'.join([
                'Limit  (cost=842.31..842.56 rows=20 width=312) (actual time=1823.421..1823.445 rows=20 loops=1)',
                '  ->  Sort  (cost=842.31..845.81 rows=1400 width=312) (actual time=1823.419..1823.432 rows=20 loops=1)',
                '        Sort Key: created_at DESC',
                '        Sort Method: top-N heapsort  Memory: 35kB',
                '        ->  Hash Join  (cost=18.50..808.72 rows=1400 width=312) (actual time=0.892..1819.234 rows=4821 loops=1)',
                '              Hash Cond: (u.id = p.user_id)',
                '              ->  Seq Scan on users u  (cost=0.00..612.40 rows=42000 width=280) (actual time=0.021..1102.445 rows=42000 loops=1)',
                '                    Filter: ((role)::text = \'editor\'::text)',
                '                    Rows Removed by Filter: 37179',
                '              ->  Hash  (cost=11.00..11.00 rows=600 width=32) (actual time=0.441..0.441 rows=600 loops=1)',
                '                    Buckets: 1024  Batches: 1  Memory Usage: 36kB',
                '                    ->  Seq Scan on permissions p  (cost=0.00..11.00 rows=600 width=32)',
                'Planning Time: 0.412 ms',
                'Execution Time: 1824.102 ms',
            ])),
            ToolCall('Bash', 'ls migrations/', '\n'.join([
                '20230801_initial_schema.sql',
                '20230915_add_sessions.sql',
                '20231102_add_audit_log.sql',
                '20231215_add_permissions.sql',
                '20240103_add_refresh_tokens.sql',
            ])),
        ],
        response="""\
The EXPLAIN ANALYZE output is very revealing. The entire 1.8 second execution time comes from
two Seq Scans:

1. **Seq Scan on users** (1,102ms out of 1,824ms total): Scanning all 42,000 users to filter
   by `role = 'editor'`. This is the smoking gun — there's no index on the `role` column.
   With 37,179 rows filtered out and only 4,821 matching, this is extremely inefficient.

2. **Hash Join with permissions**: The join itself is fast (0.4ms), but it's being done after
   the expensive seq scan.

The migration history confirms there's no migration that adds an index on `role`. The
`20231215_add_permissions.sql` migration added the permissions table but likely didn't add
the join index either.

**Fix:**
```sql
CREATE INDEX CONCURRENTLY ix_users_role ON users(role);
CREATE INDEX CONCURRENTLY ix_users_role_created_at ON users(role, created_at DESC);
```

Use `CONCURRENTLY` to avoid locking the table in production. The second composite index
covers both the filter and the sort in one scan.

After adding the index, query time should drop from ~1,800ms to ~5-15ms.
""",
        response_lean="""\
Root cause: Seq Scan on `users` — 1,102ms of 1,824ms total. Filters 42k rows for `role='editor'`, no index on `role`.

No `role` index in migration history (last: `20231215_add_permissions.sql`).

Fix:
```sql
CREATE INDEX CONCURRENTLY ix_users_role_created_at ON users(role, created_at DESC);
```
Composite covers filter + sort. Use CONCURRENTLY (no table lock). Expected: 1800ms → ~10ms.
""",
    ),
]

SESSIONS['python_refactor'] = [
    Turn(
        user_msg="I need to split the User model — it's doing too much. Show me what we're working with.",
        tool_calls=[
            ToolCall('Read', 'user.py',      FILES['src/models/user.py']),
            ToolCall('Read', 'processor.py', FILES['src/pipeline/processor.py']),
        ],
        response="""\
I can see the `User` model in `user.py` and it is indeed doing too many things. Let me break down
what it currently handles:

1. **Identity**: `id`, `email`, `username`, `first_name`, `last_name`
2. **Authentication**: `_password`, `verify_password()`, password hashing via `pwd_context`
3. **Authorization**: `role`, `permissions` relationship
4. **State/lifecycle**: `status` (ACTIVE/INACTIVE/BANNED), `is_verified`, `is_active()`
5. **Audit**: `created_at`, `updated_at`, `last_login`, `audit_logs` relationship
6. **Sessions**: `sessions` relationship

The `processor.py` file is a separate pipeline module — it doesn't seem directly related to the
User model split, unless the pipeline processes user-related events?

For the User model split, I'd suggest:
- **`User`**: identity fields only (id, email, username, name) + `to_dict()`
- **`UserCredential`**: one-to-one with User, holds `password_hash`, `verify_password()`, password setter
- **`UserProfile`**: role, status, is_verified, last_login — the "account state"
- Keep relationships on User (they're navigation properties, not responsibilities)

This follows Single Responsibility Principle. What's the driver for the split — performance,
testability, or a domain modeling concern?
""",
        response_lean="""\
`user.py` handles 5 concerns: identity, auth (password hash), authz (role/permissions), lifecycle (status/is_verified), audit (logs/timestamps).

Suggested split:
- `User` — identity only (id, email, username, name, relationships)
- `UserCredential` — 1:1 with User, owns `_password`/`verify_password()`
- `UserProfile` — role, status, is_verified, last_login

`processor.py` is unrelated pipeline — skip unless user events go through it.

What's the driver — testability, team ownership, or schema concern?
""",
    ),
    Turn(
        user_msg="Check if there are existing tests before we change anything",
        tool_calls=[
            ToolCall('Bash', 'find tests/ -name "*.py"', '\n'.join([
                'tests/__init__.py',
                'tests/conftest.py',
                'tests/models/test_user.py',
                'tests/models/test_session.py',
                'tests/services/test_user_service.py',
                'tests/services/test_auth_service.py',
                'tests/api/test_users.py',
                'tests/api/test_auth.py',
                'tests/pipeline/test_processor.py',
            ])),
            ToolCall('Bash', 'pytest tests/models/ -v', '\n'.join([
                'tests/models/test_user.py::test_password_hashing PASSED',
                'tests/models/test_user.py::test_password_verification PASSED',
                'tests/models/test_user.py::test_password_min_length PASSED',
                'tests/models/test_user.py::test_email_validation PASSED',
                'tests/models/test_user.py::test_role_coercion PASSED',
                'tests/models/test_user.py::test_full_name_hybrid PASSED',
                'tests/models/test_user.py::test_to_dict_no_password_leak PASSED',
                'tests/models/test_user.py::test_user_status_transitions PASSED',
                'tests/models/test_session.py::test_session_expiry PASSED',
                'tests/models/test_session.py::test_session_revocation PASSED',
                '',
                '10 passed in 0.42s',
            ])),
        ],
        response="""\
Good news — there's solid test coverage in place before we start the refactor.

The model tests in `tests/models/test_user.py` have 8 tests covering exactly the areas we're
splitting:
- Password hashing and verification (`test_password_hashing`, `test_password_verification`)
- Validation (`test_password_min_length`, `test_email_validation`, `test_role_coercion`)
- Hybrid properties (`test_full_name_hybrid`)
- Security (`test_to_dict_no_password_leak` — this is important, we must keep this passing)
- State (`test_user_status_transitions`)

All 10 tests pass. The strategy for the refactor should be:
1. Add the new `UserCredential` and `UserProfile` models
2. Keep all existing `User` attributes and methods working (no breaking changes yet)
3. Run the full test suite after each step
4. Once tests pass, you can deprecate the old attributes from `User` in a follow-up

The `tests/services/test_auth_service.py` and `tests/api/test_auth.py` will be the real
validation — they test behavior end-to-end, not just the model layer.
""",
        response_lean="""\
10 tests pass in `tests/models/`. Key: `test_to_dict_no_password_leak` must stay green through refactor.

Also check `tests/services/test_auth_service.py` + `tests/api/test_auth.py` — end-to-end auth coverage.

Refactor strategy:
1. Add `UserCredential` + `UserProfile` models alongside `User`
2. Delegate `User` attrs to new models (no breaking interface changes)
3. Run full suite after each step
4. Deprecate old `User` attrs in follow-up PR
""",
    ),
]

# ─────────────────────────────────────────────────────────────────────────────
# Hook runner
# ─────────────────────────────────────────────────────────────────────────────

def tok(text: str) -> int:
    return max(1, len(text) // 4)

def run_post_tool_use(tool: str, name: str, content: str) -> tuple[str, float]:
    """Returns (compressed_or_original, latency_ms)."""
    payload = json.dumps({
        'tool_name':     tool,
        'tool_input':    {'file_path': name, 'command': name, 'pattern': name},
        'tool_response': content,
    })
    t0 = time.perf_counter()
    r  = subprocess.run([NODE, str(HOOK_DIR / 'post-tool-use.js')],
                        input=payload, capture_output=True, text=True)
    ms = (time.perf_counter() - t0) * 1000
    if r.stdout.strip():
        try:
            return json.loads(r.stdout)['output'], ms
        except Exception:
            pass
    return content, ms

def run_session_start() -> tuple[str, float]:
    t0 = time.perf_counter()
    r  = subprocess.run([NODE, str(HOOK_DIR / 'session-start.js')],
                        capture_output=True, text=True)
    ms = (time.perf_counter() - t0) * 1000
    return r.stdout, ms

# ─────────────────────────────────────────────────────────────────────────────
# Simulation engine
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TurnResult:
    turn_idx:           int
    user_msg:           str
    tool_results:       list[dict]   # {tool, name, before, after, latency_ms}
    response_normal:    int          # tokens
    response_lean:      int
    input_before:       int
    input_after:        int

@dataclass
class SessionResult:
    name:          str
    turns:         list[TurnResult]
    session_start_tokens: int

def simulate_session(name: str, turns: list[Turn]) -> SessionResult:
    session_start_output, _ = run_session_start()
    ss_tokens = tok(session_start_output)
    turn_results = []

    for i, turn in enumerate(turns):
        tool_results = []
        input_before = tok(turn.user_msg)
        input_after  = tok(turn.user_msg)

        for tc in turn.tool_calls:
            before_tok = tok(tc.content)
            compressed, latency_ms = run_post_tool_use(tc.tool, tc.name, tc.content)
            after_tok = tok(compressed)
            tool_results.append({
                'tool': tc.tool, 'name': tc.name,
                'before': before_tok, 'after': after_tok,
                'latency_ms': latency_ms,
                'compressed': compressed != tc.content,
            })
            input_before += before_tok
            input_after  += after_tok

        turn_results.append(TurnResult(
            turn_idx=i+1,
            user_msg=turn.user_msg[:60] + ('…' if len(turn.user_msg) > 60 else ''),
            tool_results=tool_results,
            response_normal=tok(turn.response),
            response_lean=tok(turn.response_lean),
            input_before=input_before,
            input_after=input_after,
        ))

    return SessionResult(name=name, turns=turn_results, session_start_tokens=ss_tokens)

# ─────────────────────────────────────────────────────────────────────────────
# Scoring — five dimensions, 0–100 each
# ─────────────────────────────────────────────────────────────────────────────

COMPRESS_THRESHOLD = 30  # lines — must match post-tool-use.js

def score(results: list[SessionResult]) -> dict:
    all_tool_before = all_tool_after = 0
    all_out_normal  = all_out_lean   = 0
    all_latencies   = []
    # Distinguish: compressible (above threshold) vs small (below threshold, correctly skipped)
    compressed_count = 0    # above threshold AND compressed ✓
    missed_count     = 0    # above threshold but NOT compressed ✗  (real gap)
    small_count      = 0    # below threshold, correctly passed through (not a gap)

    for sr in results:
        for tr in sr.turns:
            all_out_normal += tr.response_normal
            all_out_lean   += tr.response_lean
            for t in tr.tool_results:
                all_tool_before += t['before']
                all_tool_after  += t['after']
                all_latencies.append(t['latency_ms'])
                # Estimate lines from token count (reverse of tok()): tokens*4/avg_chars_per_line
                est_lines = (t['before'] * 4) // 50
                if est_lines >= COMPRESS_THRESHOLD:
                    if t['compressed']:
                        compressed_count += 1
                    else:
                        missed_count += 1
                else:
                    small_count += 1  # correct pass-through

    tool_reduction = (all_tool_before - all_tool_after) / all_tool_before * 100 if all_tool_before else 0
    out_reduction  = (all_out_normal  - all_out_lean)   / all_out_normal  * 100  if all_out_normal  else 0
    avg_latency_ms = sum(all_latencies) / len(all_latencies) if all_latencies else 0

    # Coverage = compressed / (compressed + missed).  small_count excluded — correct behavior.
    compressible = compressed_count + missed_count
    coverage_pct = compressed_count / compressible * 100 if compressible > 0 else 100

    # Signal/noise: after compression, how many tokens are real content vs PITH banners (~15 tok each)
    banner_overhead = compressed_count * 15
    signal_ratio = max(0, (all_tool_after - banner_overhead) / all_tool_after * 100) if all_tool_after else 100

    # Scores (0-100):
    s_input    = min(100, tool_reduction)
    s_output   = min(100, out_reduction)
    s_latency  = max(0, 100 - (avg_latency_ms / 5))   # 25ms → 95, 100ms → 80, 500ms → 0
    s_coverage = coverage_pct
    s_signal   = signal_ratio

    overall = (s_input * 0.35 + s_output * 0.15 + s_latency * 0.20 +
               s_coverage * 0.15 + s_signal * 0.15)

    return {
        'tool_reduction': tool_reduction,
        'out_reduction':  out_reduction,
        'avg_latency_ms': avg_latency_ms,
        'coverage_pct':   coverage_pct,
        'signal_ratio':   signal_ratio,
        'compressed_count': compressed_count,
        'missed_count':     missed_count,
        'small_count':      small_count,
        'scores': {
            'input_compression': s_input,
            'output_compression': s_output,
            'hook_latency': s_latency,
            'tool_coverage': s_coverage,
            'signal_noise': s_signal,
            'overall': overall,
        },
        'tokens': {
            'tool_before': all_tool_before,
            'tool_after':  all_tool_after,
            'out_normal':  all_out_normal,
            'out_lean':    all_out_lean,
        },
    }

# ─────────────────────────────────────────────────────────────────────────────
# Verdict
# ─────────────────────────────────────────────────────────────────────────────

def verdict(overall: float) -> tuple[str, str]:
    if overall >= 85:
        return '★ STATE OF THE ART', 'Compression, latency, coverage, and signal/noise all excellent.'
    if overall >= 72:
        return '✓ PRODUCTION READY', 'Strong on input compression and latency. Minor gaps in coverage or signal.'
    if overall >= 58:
        return '~ GOOD, NOT GREAT',  'Core compression works. Latency or coverage needs improvement.'
    return '✗ NEEDS WORK', 'Significant gaps in at least one dimension.'

def bar(v: float, width: int = 25) -> str:
    filled = int(width * min(v, 100) / 100)
    return '█' * filled + '░' * (width - filled)

# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────

def report(results: list[SessionResult], sc: dict):
    W = 74
    print()
    print('━' * W)
    print('  PITH — END-TO-END SESSION SIMULATOR')
    print('━' * W)

    for sr in results:
        print()
        print(f'  SESSION: {sr.name.upper().replace("_", " ")}')
        print(f'  SessionStart injected: {sr.session_start_tokens} tokens')
        print()
        print(f'  {"Turn / Tool":<38} {"Before":>7} {"After":>7} {"ms":>5}  Reduction')
        print(f'  {"─"*38} {"──────":>7} {"──────":>7} {"──":>5}  ─────────')

        for tr in sr.turns:
            print(f'  Turn {tr.turn_idx}: {tr.user_msg[:45]}')
            for t in tr.tool_results:
                r = max(0, (t['before'] - t['after']) / t['before'] * 100) if t['before'] else 0
                flag = '' if t['compressed'] else '  (pass-through)'
                print(f'    {t["tool"]:<6} {t["name"]:<30} {t["before"]:>7,} {t["after"]:>7,} {t["latency_ms"]:>5.0f}  '
                      f'{bar(r,14)} {r:.0f}%{flag}')
            in_r = max(0, (tr.input_before - tr.input_after) / tr.input_before * 100) if tr.input_before else 0
            out_r= max(0, (tr.response_normal - tr.response_lean) / tr.response_normal * 100) if tr.response_normal else 0
            print(f'    {"INPUT TOTAL":<37} {tr.input_before:>7,} {tr.input_after:>7,}        {in_r:.0f}% saved')
            print(f'    {"OUTPUT (lean vs normal)":<37} {tr.response_normal:>7,} {tr.response_lean:>7,}        {out_r:.0f}% saved')

    t = sc['tokens']
    print()
    print('━' * W)
    print('  AGGREGATE ACROSS ALL SESSIONS')
    print('━' * W)
    print()
    print(f'  Tool result tokens:  {t["tool_before"]:>7,}  →  {t["tool_after"]:>7,}'
          f'   ({sc["tool_reduction"]:.0f}% reduction)')
    print(f'  Response tokens:     {t["out_normal"]:>7,}  →  {t["out_lean"]:>7,}'
          f'   ({sc["out_reduction"]:.0f}% reduction)')
    print(f'  Avg hook latency:    {sc["avg_latency_ms"]:.1f}ms')
    print(f'  Tool call coverage:  {sc["coverage_pct"]:.0f}% of calls compressed')
    print(f'  Signal/noise ratio:  {sc["signal_ratio"]:.0f}% of compressed tokens are signal')

    s = sc['scores']
    print()
    print('  SCORING (weighted)')
    print('  ─' * 37)
    dims = [
        ('Input compression  (35%)', s['input_compression']),
        ('Output compression (15%)', s['output_compression']),
        ('Hook latency       (20%)', s['hook_latency']),
        ('Tool coverage      (15%)', s['tool_coverage']),
        ('Signal/noise       (15%)', s['signal_noise']),
    ]
    for label, v in dims:
        print(f'  {label:<28} {bar(v,25)} {v:.0f}/100')

    print()
    print(f'  {"OVERALL":<28} {bar(s["overall"],25)} {s["overall"]:.0f}/100')
    print()

    label, explanation = verdict(s['overall'])
    print(f'  VERDICT: {label}')
    print(f'  {explanation}')
    print()
    print('  Honest caveats:')
    print(f'  • {sc["compressed_count"]} calls compressed, '
          f'{sc["small_count"]} correctly skipped (below 30-line threshold), '
          f'{sc["missed_count"]} missed')
    print(f'  • Output reduction measured on written examples — real Claude filler varies')
    print(f'  • Latency measured on local node process — in Claude Code, hook runs async, adds ~0ms perceived')
    print(f'  • Token counts use chars/4 approximation — actual BPE within ±8%')
    print()
    print('━' * W)
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print('\nRunning sessions...', end='', flush=True)
    results = []
    for name, turns in SESSIONS.items():
        print(f'  {name}...', end='', flush=True)
        results.append(simulate_session(name, turns))
    print()

    sc = score(results)
    report(results, sc)


if __name__ == '__main__':
    main()
