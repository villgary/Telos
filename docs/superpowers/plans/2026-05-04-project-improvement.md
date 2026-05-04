# Project Improvement Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve Telos project quality through testing infrastructure, frontend architecture cleanup, configuration validation, and database migration setup.

**Architecture:** Incremental improvements targeting the highest-impact areas: testing coverage, code organization, and production-readiness configuration.

**Tech Stack:** FastAPI, React 18, TypeScript, PostgreSQL, SQLAlchemy, Pytest, Vitest

---

## Phase 1: Testing Infrastructure

### Task 1: Setup Backend Test Infrastructure

**Files:**
- Create: `backend/tests/conftest.py` (extends existing)
- Create: `backend/tests/test_config.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add pytest and testing dependencies to requirements.txt**

Add to `backend/requirements.txt`:
```
pytest==8.3.4
pytest-asyncio==0.25.2
pytest-cov==6.0.0
httpx==0.27.2
```

- [ ] **Step 2: Verify existing conftest.py content**

```python
# backend/tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base

TEST_DATABASE_URL = "sqlite:///./test.db"

@pytest.fixture(scope="function")
def db_engine():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture(scope="function")
def db_session(db_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()
```

- [ ] **Step 3: Commit**

```bash
cd /Users/jyb/projects/telos
git add backend/requirements.txt backend/tests/conftest.py
git commit -m "test: add pytest infrastructure with conftest fixtures"
```

---

### Task 2: Add Backend Config Validation Test

**Files:**
- Create: `backend/tests/test_config.py`

- [ ] **Step 1: Write failing test for config validation**

```python
# backend/tests/test_config.py
import os
import pytest
from pydantic import ValidationError

def test_database_url_required():
    """DATABASE_URL must be set or raise ValidationError."""
    from backend.config import Settings
    # Clear env
    original = os.environ.get("DATABASE_URL")
    if original:
        del os.environ["DATABASE_URL"]
    try:
        with pytest.raises(ValidationError):
            Settings()
    finally:
        if original:
            os.environ["DATABASE_URL"] = original
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jyb/projects/telos && python -m pytest backend/tests/test_config.py -v`
Expected: FAIL - module 'backend.config' has no attribute 'Settings'

- [ ] **Step 3: Create minimal config module**

```python
# backend/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    database_url: str
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_ssl_mode: str = "prefer"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Update database.py to use config**

Modify `backend/database.py:1-12`:
```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config import get_settings

settings = get_settings()
DATABASE_URL = settings.database_url

is_sqlite = DATABASE_URL.startswith("sqlite")
if not is_sqlite:
    os.environ["DB_SSLMODE"] = settings.db_ssl_mode
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/jyb/projects/telos && python -m pytest backend/tests/test_config.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/config.py backend/database.py backend/tests/test_config.py
git commit -m "feat: add Pydantic settings for config validation"
```

---

### Task 3: Add Service Layer Tests

**Files:**
- Create: `backend/tests/test_diff_engine.py` (extends existing with more cases)

- [ ] **Step 1: Write failing test for diff engine**

```python
# backend/tests/test_diff_engine.py
import pytest
from backend.services.diff_engine import DiffEngine

def test_detect_new_accounts():
    engine = DiffEngine()
    old_accounts = [{"username": "alice", "uid": 1001}]
    new_accounts = [{"username": "alice", "uid": 1001}, {"username": "bob", "uid": 1002}]
    diff = engine.compute_diff(old_accounts, new_accounts, "linux")
    assert any(d["change_type"] == "added" and d["username"] == "bob" for d in diff["accounts"])

def test_detect_removed_accounts():
    engine = DiffEngine()
    old_accounts = [{"username": "alice", "uid": 1001}, {"username": "bob", "uid": 1002}]
    new_accounts = [{"username": "alice", "uid": 1001}]
    diff = engine.compute_diff(old_accounts, new_accounts, "linux")
    assert any(d["change_type"] == "removed" and d["username"] == "bob" for d in diff["accounts"])

def test_detect_modified_accounts():
    engine = DiffEngine()
    old_accounts = [{"username": "alice", "uid": 1001, "home": "/home/alice"}]
    new_accounts = [{"username": "alice", "uid": 1001, "home": "/var/alice"}]
    diff = engine.compute_diff(old_accounts, new_accounts, "linux")
    assert any(d["change_type"] == "modified" and d["username"] == "alice" for d in diff["accounts"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/jyb/projects/telos && python -m pytest backend/tests/test_diff_engine.py -v`
Expected: FAIL - test_detect_new_accounts, test_detect_removed_accounts, test_detect_modified_accounts fail

- [ ] **Step 3: Implement DiffEngine methods**

```python
# backend/services/diff_engine.py - add methods
def compute_diff(self, old_accounts, new_accounts, account_type):
    old_map = {a["username"]: a for a in old_accounts}
    new_map = {a["username"]: a for a in new_accounts}
    changes = []
    
    for username, new_acc in new_map.items():
        if username not in old_map:
            changes.append({**new_acc, "change_type": "added"})
        elif old_map[username] != new_acc:
            changes.append({**new_acc, "change_type": "modified", "old": old_map[username]})
    
    for username in old_map:
        if username not in new_map:
            changes.append({**old_map[username], "change_type": "removed"})
    
    return {"accounts": changes}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/jyb/projects/telos && python -m pytest backend/tests/test_diff_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/diff_engine.py backend/tests/test_diff_engine.py
git commit -m "test: add diff engine account change detection tests"
```

---

## Phase 2: Frontend Architecture

### Task 4: Setup Vitest for Frontend Testing

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Add Vitest and testing dependencies to package.json**

Add to `frontend/package.json` devDependencies:
```json
"vitest": "^2.1.0",
"@vitest/ui": "^2.1.0",
"jsdom": "^25.0.0",
"@testing-library/react": "^16.0.0",
"@testing-library/jest-dom": "^6.5.0"
```

- [ ] **Step 2: Create Vitest config**

```javascript
// frontend/vitest.config.ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
    },
  },
})
```

- [ ] **Step 3: Create test setup file**

```typescript
// frontend/src/test/setup.ts
import '@testing-library/jest-dom'
```

- [ ] **Step 4: Update package.json scripts**

Add to `scripts`:
```json
"test": "vitest",
"test:ui": "vitest --ui",
"test:coverage": "vitest --coverage"
```

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/vitest.config.ts frontend/src/test/setup.ts
git commit -m "test: add Vitest for frontend unit testing"
```

---

### Task 5: Split App.tsx with Lazy Loading

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/components/AppLayout.tsx`
- Create: `frontend/src/components/Layout.tsx`

- [ ] **Step 1: Create Layout component**

```typescript
// frontend/src/components/Layout.tsx
import { Layout, Menu, Badge, Dropdown, List, Tag, Typography, Button, Space, Segmented } from 'antd'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
// ... imports for icons

const { Header, Sider, Content } = Layout
const { Text } = Typography

interface LayoutProps {
  children: React.ReactNode
  viewMode: 'operator' | 'admin'
  setViewMode: (v: 'operator' | 'admin') => void
}

export function AppLayout({ viewMode, setViewMode, children }: LayoutProps) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  
  // ... menu items, alert handling, etc.
  // Move existing AppLayout logic here
  
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header>...</Header>
      <Layout>
        <Sider>{/* menu */}</Sider>
        <Content>{children}</Content>
      </Layout>
    </Layout>
  )
}
```

- [ ] **Step 2: Update App.tsx to use lazy loading and Layout**

```typescript
// frontend/src/App.tsx
import { Routes, Route } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { AppLayout } from './components/Layout'
import { Spin } from 'antd'

// Lazy load all page components
const Login = lazy(() => import('./pages/Login'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Assets = lazy(() => import('./pages/Assets'))
// ... other lazy imports

function LoadingFallback() {
  return <div style={{ display: 'flex', justifyContent: 'center', padding: 50 }}><Spin /></div>
}

function App() {
  const [viewMode, setViewMode] = useState<'operator' | 'admin'>('admin')
  
  return (
    <Suspense fallback={<LoadingFallback />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/*" element={
          <AppLayout viewMode={viewMode} setViewMode={setViewMode}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/assets" element={<Assets />} />
              {/* ... other routes */}
            </Routes>
          </AppLayout>
        } />
      </Routes>
    </Suspense>
  )
}

export default App
```

- [ ] **Step 3: Verify build still works**

Run: `cd frontend && npm run build`
Expected: Build completes without errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/src/components/AppLayout.tsx
git commit -m "refactor: split App.tsx with lazy loading routes and Layout component"
```

---

### Task 6: Add Frontend Unit Test Example

**Files:**
- Create: `frontend/src/pages/__tests__/Login.test.tsx`

- [ ] **Step 1: Write failing test for Login page**

```typescript
// frontend/src/pages/__tests__/Login.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import Login from '../Login'

describe('Login', () => {
  it('renders login form', () => {
    render(<Login />)
    expect(screen.getByPlaceholderText(/username/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- --run src/pages/__tests__/Login.test.tsx`
Expected: FAIL - no test environment setup

- [ ] **Step 3: Fix Vitest environment issue if any**

The test runner should work after Task 4 setup. Verify with:
Run: `cd frontend && npm run test -- --run src/pages/__tests__/Login.test.tsx`
Expected: PASS or skip if Login component needs fixes

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/__tests__/Login.test.tsx
git commit -m "test: add Login page unit test"
```

---

## Phase 3: Database Migrations

### Task 7: Setup Alembic for Database Migrations

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/` directory with env.py, script.py.mako
- Modify: `backend/database.py`

- [ ] **Step 1: Initialize Alembic**

Run: `cd /Users/jyb/projects/telos && alembic init backend/alembic`
Expected: Creates alembic/ directory with env.py, script.py.mako, etc.

- [ ] **Step 2: Configure alembic.ini**

```ini
# backend/alembic.ini
[alembic]
script_location = backend/alembic
prepend_sys_path = .
version_path_separator = os

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

- [ ] **Step 3: Update alembic env.py for SQLAlchemy 2.0**

```python
# backend/alembic/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.database import Base
from backend import models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_config().get("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
```

- [ ] **Step 4: Update main.py to remove create_all, use Alembic**

Modify `backend/main.py:44-46`:
```python
# Remove init_db() call that uses create_all
# Instead rely on Alembic migrations
# init_db() is called in lifespan for first run only
```

- [ ] **Step 5: Create initial migration**

Run: `cd /Users/jyb/projects/telos && alembic revision --autogenerate -m "initial migration"`
Expected: Creates `backend/alembic/versions/xxxx_initial_migration.py`

- [ ] **Step 6: Commit**

```bash
git add backend/alembic.ini backend/alembic/ backend/main.py
git commit -m "feat: setup Alembic for database migrations"
```

---

## Phase 4: Error Handling Standardization

### Task 8: Create Standard Error Response Schema

**Files:**
- Create: `backend/schemas/errors.py`
- Modify: `backend/routers/auth.py` (example)
- Modify: `backend/main.py`

- [ ] **Step 1: Create standard error schema**

```python
# backend/schemas/errors.py
from pydantic import BaseModel
from typing import Optional, Any

class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
    trace_id: Optional[str] = None

class ValidationErrorItem(BaseModel):
    loc: tuple[str, ...]
    msg: str
    type: str

class ValidationErrorResponse(BaseModel):
    detail: list[ValidationErrorItem]
    code: str = "validation_error"
```

- [ ] **Step 2: Update global exception handler in main.py**

Modify `backend/main.py:269-286` to use ErrorResponse:
```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    trace_id = get_trace_id()
    logger.exception("unhandled-exception", trace_id=trace_id, path=request.url.path, exc_type=type(exc).__name__)
    
    if hasattr(exc, "status_code"):
        return JSONResponse(status_code=getattr(exc, "status_code", 500), content={"detail": str(exc), "trace_id": trace_id})
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "服务器内部错误，请联系管理员", "trace_id": trace_id},
    )
```

- [ ] **Step 3: Commit**

```bash
git add backend/schemas/errors.py backend/main.py
git commit -m "feat: standardize error response format with trace IDs"
```

---

## Summary

| Task | Description | Files Modified |
|------|-------------|----------------|
| 1 | Backend test infrastructure | requirements.txt, conftest.py |
| 2 | Config validation with Pydantic | config.py, database.py, test_config.py |
| 3 | Diff engine service tests | test_diff_engine.py, diff_engine.py |
| 4 | Frontend Vitest setup | package.json, vitest.config.ts, setup.ts |
| 5 | Split App.tsx with lazy loading | App.tsx, Layout.tsx, AppLayout.tsx |
| 6 | Frontend unit test example | Login.test.tsx |
| 7 | Alembic migrations setup | alembic.ini, alembic/, main.py |
| 8 | Standardized error responses | errors.py, main.py |
