# Monorepo Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify vcoo-onboarding (backend), vcoo-dashboard (frontend), and vcoo-template into a single monorepo with `apps/`, `packages/`, `infra/` structure, then clean up the submodule that was set up temporarily.

**Architecture:** Three apps directories under `apps/` (backend, frontend), shared code under `packages/`, infra config under `infra/`. Vercel deploys each `apps/*` independently via Root Directory config.

**Tech Stack:** Python (FastAPI), TypeScript (React/Vite), Docker, Vercel

---

### Task 1: Commit current state

Remove the submodule that was set up in the previous session, commit all pending changes, so we start the migration from a clean state.

**Files:**
- Modify: `.gitmodules`
- Modify: `.gitignore`
- Delete: `frontend/` (submodule reference)
- Add: `.env.production`

- [ ] **Step 1: Remove the submodule reference**

```bash
cd /home/ubuntu/versus/vcoo-onboarding
git submodule deinit frontend
git rm frontend
rm -rf .gitmodules
rm -rf .git/modules/frontend
```

- [ ] **Step 2: Add frontend/ to .gitignore so the empty directory doesn't get tracked**

Add to `.gitignore`:
```
frontend/
```

- [ ] **Step 3: Commit current state**

```bash
git add -A
git commit -m "chore: back to clean slate before monorepo migration"
```

---

### Task 2: Create directory structure

**Files:**
- Create: `apps/`
- Create: `packages/`
- Create: `infra/`

- [ ] **Step 1: Create directories**

```bash
cd /home/ubuntu/versus/vcoo-onboarding
mkdir -p apps packages infra docs/superpowers/plans
```

- [ ] **Step 2: Commit empty structure**

```bash
git add apps/ packages/ infra/ docs/
git commit -m "chore: create monorepo directory structure"
```

---

### Task 3: Move backend into apps/

**Files:**
- Move: `backend/` → `apps/backend/`
- Move: `api/` stays at root (Vercel entrypoint)

- [ ] **Step 1: Move the backend directory**

```bash
cd /home/ubuntu/versus/vcoo-onboarding
mv backend apps/backend
```

- [ ] **Step 2: Commit**

```bash
git add apps/backend
git add -u  # track deletions of old backend/
git commit -m "feat: move backend into apps/backend"
```

---

### Task 4: Move agent, vsd into packages/

**Files:**
- Move: `agent/` → `packages/agent/`
- Move: `vsd/` → `packages/vsd/`

- [ ] **Step 1: Move directories**

```bash
cd /home/ubuntu/versus/vcoo-onboarding
mv agent packages/agent
mv vsd packages/vsd
```

- [ ] **Step 2: Update any relative paths inside packages that reference `../`**

Check `packages/agent/install.sh` and `packages/agent/agent_http.py` for references to `../backend/` or similar and update them to `../apps/backend/`.

- [ ] **Step 3: Commit**

```bash
git add packages/
git add -u
git commit -m "feat: move agent, vsd into packages/"
```

---

### Task 5: Move infra files into infra/

**Files:**
- Move: `docker-compose.yml` → `infra/docker-compose.yml`
- Move: `Dockerfile.backend` → `infra/Dockerfile.backend`
- Move: `vercel.json` → `infra/vercel.json` (keep a copy at root for Vercel)
- Move: `supabase.sql` → `infra/supabase/supabase.sql`
- Move: `supabase/` → `infra/supabase/`

- [ ] **Step 1: Move infra files**

```bash
cd /home/ubuntu/versus/vcoo-onboarding
mkdir -p infra/supabase
mv docker-compose.yml infra/
mv Dockerfile.backend infra/
cp vercel.json infra/vercel.json  # keep original at root for Vercel
mv supabase.sql infra/supabase/ 2>/dev/null || true
mv supabase/ infra/ 2>/dev/null || true
```

- [ ] **Step 2: Commit**

```bash
git add infra/
git add -u
git commit -m "chore: move infra files into infra/"
```

---

### Task 6: Integrate vcoo-dashboard into apps/frontend

**Files:**
- Create: `apps/frontend/` (copy from existing vcoo-dashboard repo)

- [ ] **Step 1: Copy the vcoo-dashboard code**

```bash
cd /home/ubuntu/versus/vcoo-onboarding
cp -r /home/ubuntu/vcoo-dashboard/. apps/frontend/
rm -rf apps/frontend/node_modules apps/frontend/dist
```

- [ ] **Step 2: Create .env for local dev**

Write `apps/frontend/.env`:
```
VITE_API_URL=http://10.0.0.1:8000
```

- [ ] **Step 3: Build to verify it works**

```bash
cd apps/frontend && npm install && npm run build
```

- [ ] **Step 4: Commit**

```bash
cd /home/ubuntu/versus/vcoo-onboarding
git add apps/frontend
git commit -m "feat: integrate vcoo-dashboard into apps/frontend"
```

---

### Task 7: Integrate vcoo-template into packages/template

**Files:**
- Create: `packages/template/` (copy from existing vcoo-template repo)

- [ ] **Step 1: Copy the template code**

```bash
cd /home/ubuntu/versus/vcoo-onboarding
cp -r /home/ubuntu/versus/vcoo-template/. packages/template/
```

- [ ] **Step 2: Commit**

```bash
git add packages/template
git commit -m "feat: integrate vcoo-template into packages/template"
```

---

### Task 8: Update api/[...slug].py import path

**Files:**
- Modify: `api/[...slug].py`

The Vercel entrypoint imports `backend.main` but now backend lives at `apps/backend/`.

- [ ] **Step 1: Update the sys.path and import**

Edit `api/[...slug].py`:

```python
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'apps'))

from backend.main import app
handler = app
```

- [ ] **Step 2: Test locally**

```bash
cd /home/ubuntu/versus/vcoo-onboarding
python -c "from backend.main import app; print('OK')"
```

Run this from the `apps/` directory to verify the import works.

- [ ] **Step 3: Commit**

```bash
git add api/[...slug].py
git commit -m "fix: update Vercel entrypoint import path for monorepo"
```

---

### Task 9: Update Dockerfile.backend paths

**Files:**
- Modify: `infra/Dockerfile.backend`

- [ ] **Step 1: Update COPY paths**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY apps/backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY apps/backend /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Commit**

```bash
git add infra/Dockerfile.backend
git commit -m "fix: update Dockerfile paths for monorepo"
```

---

### Task 10: Update docker-compose.yml paths

**Files:**
- Modify: `infra/docker-compose.yml`

- [ ] **Step 1: Update build context, dockerfile, and env_file paths**

```yaml
version: '3.8'
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: vcoo
    volumes:
      - vcoo-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  backend:
    build:
      context: ..
      dockerfile: infra/Dockerfile.backend
    env_file:
      - ../apps/backend/.env
    environment:
      POSTGRES_URL: postgresql://postgres:postgres@db:5432/vcoo
    depends_on:
      - db
    ports:
      - "8000:8000"

volumes:
  vcoo-data:
```

- [ ] **Step 2: Verify Docker build still works**

```bash
cd /home/ubuntu/versus/vcoo-onboarding/infra
docker compose build backend
```

- [ ] **Step 3: Commit**

```bash
cd /home/ubuntu/versus/vcoo-onboarding
git add infra/docker-compose.yml
git commit -m "fix: update docker-compose paths for monorepo"
```

---

### Task 11: Update .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Consolidate gitignore for monorepo structure**

```gitignore
__pycache__/
*.pyc
.vcoo-agent/
agent.token
master.key
.env
/tmp/
.vercel
node_modules/
dist/

# Monorepo-specific
apps/*/.env
packages/*/node_modules/
packages/*/dist/
infra/supabase/.env

# Test files
apps/backend/test*.py
apps/backend/test.db
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: update gitignore for monorepo structure"
```

---

### Task 12: Update README.md

**Files:**
- Modify: `README.md`

Update to reflect the new monorepo structure, remove references to submodules, document the `apps/` layout and how deploys work.

- [ ] **Step 1: Commit**

```bash
git add README.md
git commit -m "docs: update README with monorepo structure"
```

---

### Task 13: Restart Docker container

- [ ] **Step 1: Rebuild and restart**

```bash
cd /home/ubuntu/versus/vcoo-onboarding/infra
docker compose down
docker compose up -d --build backend
sleep 3
curl -s http://localhost:8000/healthz
```

- [ ] **Step 2: Verify backend works**

```bash
curl -s http://localhost:8000/vcoos | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'OK — {len(d)} VCOOs')"
```
