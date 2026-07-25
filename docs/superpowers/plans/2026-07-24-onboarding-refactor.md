# Onboarding Refactor — Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to implement. Steps use checkbox syntax.

**Goal:** Refactor shared auth, centralize auto-trigger, deprecate /poll, add security tests, rename modules, add credential encryption.

**Architecture:** Changes to `main.py`, `crud.py`, `onboarding.py`, `tests/`, `docs/SPEC.md`. All tasks independent — parallel execution safe.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, pytest

## Global Constraints

- Backend imports flat/top-level
- Run from `apps/backend/`
- Spanish identifiers/comments
- TDD: test first, then code
- All tests must pass after each task

---

### Task 1: Shared auth dependency (`get_current_client`)

**Files:**
- Modify: `apps/backend/main.py` — add `get_current_client` Depends, refactor 6 endpoints
- Test: `apps/backend/tests/test_onboarding.py` — verify refactored auth still works

**Interfaces:**
- Produces: `get_current_client(identifier, authorization, db) → dict` with `vcoo_id`, `email`, `is_operator`, `vcoo_name`

**Changes:**
1. Add `get_current_client()` function before route definitions
2. Replace inline auth in: `/setup/{identifier}/verify`, `/advance`, `/set-provider`, `/start-pair-whatsapp`, `/whatsapp-qr`
3. Partial refactor of `GET /setup/{identifier}` (has 3-case auth, keep as-is)

---

### Task 2: Centralize auto-trigger helper

**Files:**
- Modify: `apps/backend/crud.py` — add `auto_enqueue_next(db, agent, vcoo_id)`
- Modify: `apps/backend/main.py` — replace inline auto-trigger blocks with helper calls

**Interfaces:**
- Produces: `auto_enqueue_next(db, agent_id, vcoo_id) → Optional[str]` returns cmd_id or None

**Changes:**
1. Add `auto_enqueue_next` to `crud.py`
2. Replace inline blocks in `process_agent_result` (crud.py), `oauth_callback` (main.py), `/register` (main.py)

---

### Task 3: Deprecate /poll + unify with /tick

**Files:**
- Modify: `apps/backend/main.py` — add Deprecation header to /poll, create shared helper

**Changes:**
1. Add `Deprecation: true` and `Sunset: Sat, 31 Jan 2027 00:00:00 GMT` headers to `/poll` response
2. `/poll` delegates to same command logic as `/tick`

---

### Task 4: Security tests

**Files:**
- Modify: `apps/backend/tests/test_utils.py` — add rate limit test for /register
- Modify: `apps/backend/tests/test_onboarding.py` — add path traversal test

---

### Task 5: Rename module IDs (google-drive, gmail)

**Files:**
- Modify: `apps/backend/onboarding.py` — add alias support in MODULE_STEPS, MODULE_LABELS

**Changes:**
- `office` → also accepts `google-drive`
- `mail` → also accepts `gmail`
- `planner` → also accepts `trello`

---

### Task 6: Encrypt creds endpoint

**Files:**
- Modify: `apps/backend/main.py` — add POST /setup/{id}/encrypt-creds

**Changes:**
- New endpoint that takes `{service, credentials_dict}`, encrypts with agent's encryption_key, stores result
