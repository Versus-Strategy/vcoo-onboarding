# VCOO Supervisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build modular vcoo-supervisor (replaces versusd + health-reporter + heartbeat), audit log, and metrics display in client detail page.

**Architecture:** Python supervisor with plugin system (health reporter, watchdog, updater). Backend adds AuditLog model + endpoints. Frontend displays metrics + audit in existing DetalleClientePage.

**Tech Stack:** Python 3.11 (supervisor), FastAPI/SQLAlchemy (backend), React/TypeScript (frontend)

---

### Task 1: Add AuditLog model to backend

**Files:**
- Modify: `apps/backend/models.py`
- Modify: `apps/backend/crud.py`

- [ ] **Step 1: Add AuditLog model to models.py**

Add after the `OnboardingState` class:

```python
class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action = Column(String(64), nullable=False, index=True)
    actor_email = Column(String(255), nullable=True)
    vcoo_id = Column(String(36), nullable=True, index=True)
    metadata = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
```

- [ ] **Step 2: Add version columns to Agent model**

Find the `Agent` class and add:

```python
template_version = Column(String(32), nullable=True)
supervisor_version = Column(String(32), nullable=True)
```

- [ ] **Step 3: Add CRUD functions to crud.py**

```python
def create_audit_log(db: Session, action: str, actor_email: str = None, vcoo_id: str = None, metadata: dict = None):
    log = AuditLog(
        action=action,
        actor_email=actor_email,
        vcoo_id=vcoo_id,
        metadata=json.dumps(metadata) if metadata else None,
    )
    db.add(log)
    db.commit()
    return log

def get_audit_log_for_vcoo(db: Session, vcoo_id: str, limit: int = 20):
    return db.query(AuditLog).filter(
        AuditLog.vcoo_id == vcoo_id
    ).order_by(AuditLog.created_at.desc()).limit(limit).all()
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend/models.py apps/backend/crud.py
git commit -m "feat: add AuditLog model and version columns to Agent"
```

---

### Task 2: Write audit events from existing endpoints

**Files:**
- Modify: `apps/backend/main.py`

- [ ] **Step 1: Add audit writes to key endpoints**

In `POST /vcoo` (create_vcoo), after successful creation:
```python
crud.create_audit_log(db, action="vcoo.created", actor_email="operator", vcoo_id=str(vcoo.id), metadata={"name": name})
```

In `POST /vcoo/{vcoo_id}/regenerate-token` (regenerate_token), after success:
```python
crud.create_audit_log(db, action="token.regenerated", vcoo_id=vcoo_id)
```

In `DELETE /vcoo/{vcoo_id}` (delete_vcoo), before deletion:
```python
crud.create_audit_log(db, action="vcoo.deleted", vcoo_id=vcoo_id, metadata={"name": v.name})
```

In `POST /auth/client/register` (client_register), after success:
```python
crud.create_audit_log(db, action="client.registered", actor_email=payload.email, vcoo_id=vcoo_id)
```

In the health report endpoint (`POST /agent/{agent_id}/health`), extract version from payload and store:
```python
if payload.get("template_version"):
    crud.update_agent_version(db, agent_id, template_version=payload.get("template_version"), supervisor_version=payload.get("supervisor_version"))
```

- [ ] **Step 2: Add update_agent_version to crud.py**

```python
def update_agent_version(db: Session, agent_id: str, template_version: str = None, supervisor_version: str = None):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        return
    if template_version:
        agent.template_version = template_version
    if supervisor_version:
        agent.supervisor_version = supervisor_version
    db.commit()
```

- [ ] **Step 3: Commit**

```bash
git add apps/backend/main.py apps/backend/crud.py
git commit -m "feat: write audit log from endpoints + store agent versions"
```

---

### Task 3: Add audit endpoint

**Files:**
- Modify: `apps/backend/main.py`

- [ ] **Step 1: Add GET /vcoo/{vcoo_id}/audit endpoint**

```python
@app.get("/vcoo/{vcoo_id}/audit")
def get_vcoo_audit(vcoo_id: str, db: Session = Depends(get_db)):
    logs = crud.get_audit_log_for_vcoo(db, vcoo_id)
    return {
        "audit_log": [
            {
                "id": str(log.id),
                "action": log.action,
                "actor_email": log.actor_email,
                "metadata": json.loads(log.metadata) if log.metadata else None,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
    }
```

- [ ] **Step 2: Commit**

```bash
git add apps/backend/main.py
git commit -m "feat: add GET /vcoo/{id}/audit endpoint"
```

---

### Task 4: Add metrics card to DetalleClientePage

**Files:**
- Modify: `apps/frontend/src/pages/operador/Clientes/DetalleCliente.tsx`

- [ ] **Step 1: Add metrics section after "Estado del Agente" block**

Insert after the agent status div (after line ~210):

```tsx
{/* 📊 Server metrics */}
{agentInfo?.health_payload ? (
  <div className="bg-white rounded-lg shadow p-6">
    <h2 className="text-lg font-semibold text-gray-900 mb-4">📊 Métricas del servidor</h2>
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
      <div>
        <span className="text-sm text-gray-500">Hostname</span>
        <p className="text-sm font-medium text-gray-900">{(agentInfo.health_payload as Record<string,unknown>)?.hostname as string || '—'}</p>
      </div>
      <div>
        <span className="text-sm text-gray-500">Disco</span>
        <p className="text-sm font-medium text-gray-900">
          {(agentInfo.health_payload as Record<string,unknown>)?.disk_used_pct != null
            ? `${(agentInfo.health_payload as Record<string,unknown>).disk_used_pct}%`
            : '—'}
        </p>
      </div>
      <div>
        <span className="text-sm text-gray-500">Uptime</span>
        <p className="text-sm font-medium text-gray-900">
          {(agentInfo.health_payload as Record<string,unknown>)?.uptime_seconds
            ? `${Math.floor((agentInfo.health_payload as Record< string,unknown>).uptime_seconds as number / 3600)}h ${Math.floor(((agentInfo.health_payload as Record<string,unknown>).uptime_seconds as number % 3600) / 60)}m`
            : '—'}
        </p>
      </div>
      <div>
        <span className="text-sm text-gray-500">Hermes</span>
        <p className="text-sm font-medium text-gray-900">
          {(agentInfo.health_payload as Record<string,unknown>)?.hermes_running ? '● En ejecución' : '○ Detenido'}
        </p>
      </div>
      <div>
        <span className="text-sm text-gray-500">Template</span>
        <p className="text-sm font-medium text-gray-900">{(agentInfo.health_payload as Record<string,unknown>)?.template_version as string || '—'}</p>
      </div>
      <div>
        <span className="text-sm text-gray-500">Supervisor</span>
        <p className="text-sm font-medium text-gray-900">{(agentInfo.health_payload as Record<string,unknown>)?.supervisor_version as string || '—'}</p>
      </div>
    </div>
  </div>
) : (
  <div className="bg-white rounded-lg shadow p-6">
    <h2 className="text-lg font-semibold text-gray-900 mb-4">📊 Métricas del servidor</h2>
    <p className="text-sm text-gray-500">Esperando primer reporte de métricas...</p>
  </div>
)}
```

- [ ] **Step 2: Commit**

```bash
git add apps/frontend/src/pages/operador/Clientes/DetalleCliente.tsx
git commit -m "feat: add server metrics card to DetalleClientePage"
```

---

### Task 5: Add audit timeline to DetalleClientePage

**Files:**
- Modify: `apps/frontend/src/pages/operador/Clientes/DetalleCliente.tsx`

- [ ] **Step 1: Add state + fetch for audit log**

After the existing estado/tokenData state declarations, add:

```tsx
const [auditLog, setAuditLog] = useState<Array<{action: string; actor_email: string | null; metadata: Record<string, unknown> | null; created_at: string}>>([]);

// Add to the cargarDatos function, after estadoRes/tokenRes:
try {
  const auditRes = await apiClient.get(`/vcoo/${id}/audit`);
  setAuditLog(auditRes.data.audit_log as typeof auditLog);
} catch {}
```

- [ ] **Step 2: Add timeline UI before "Zona de peligro" section**

Insert before the delete client div:

```tsx
{/* 📋 Activity log */}
{auditLog.length > 0 && (
  <div className="bg-white rounded-lg shadow p-6">
    <h2 className="text-lg font-semibold text-gray-900 mb-4">📋 Actividad reciente</h2>
    <div className="space-y-3">
      {auditLog.map((entry, idx) => (
        <div key={idx} className="flex items-start gap-3 text-sm">
          <div className="w-2 h-2 rounded-full bg-primary-500 mt-1.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-gray-900">{entry.action}</p>
            <p className="text-gray-500 text-xs">
              {entry.created_at ? new Date(entry.created_at).toLocaleString('es-ES') : ''}
              {entry.actor_email ? ` — ${entry.actor_email}` : ''}
            </p>
          </div>
        </div>
      ))}
    </div>
  </div>
)}
```

- [ ] **Step 3: Commit**

```bash
git add apps/frontend/src/pages/operador/Clientes/DetalleCliente.tsx
git commit -m "feat: add audit timeline to DetalleClientePage"
```

---

### Task 6: Build vcoo-supervisor package

**Files:**
- Create: `packages/vcoo-supervisor/supervisor.py`
- Create: `packages/vcoo-supervisor/plugins/__init__.py`
- Create: `packages/vcoo-supervisor/plugins/health_reporter.py`
- Create: `packages/vcoo-supervisor/plugins/watchdog.py`
- Create: `packages/vcoo-supervisor/plugins/updater.py`
- Create: `packages/vcoo-supervisor/config.yaml`
- Create: `packages/vcoo-supervisor/vcoo-supervisor.service`

- [ ] **Step 1: Create supervisor core**

`packages/vcoo-supervisor/supervisor.py`:

```python
#!/usr/bin/env python3
"""VCOO Supervisor — modular agent health reporter, watchdog, and updater."""

import os, sys, time, importlib, logging, signal, json
from pathlib import Path

CONFIG_PATHS = [
    "/etc/vcoo/supervisor.json",
    os.path.expanduser("~/.vcoo/supervisor.json"),
    "supervisor.json",
]

class Supervisor:
    def __init__(self, config: dict):
        self.config = config
        self.plugins: list = []
        self.running = True
        self.last_tick: dict[str, float] = {}

    def load_plugins(self):
        plugin_dir = Path(__file__).parent / "plugins"
        sys.path.insert(0, str(plugin_dir))
        for name, cfg in self.config.get("plugins", {}).items():
            if not cfg.get("enabled", True):
                continue
            mod = importlib.import_module(name)
            plugin = mod.Plugin()
            plugin.start(cfg)
            self.plugins.append(plugin)
            self.last_tick[name] = 0

    def run(self):
        self.load_plugins()
        while self.running:
            now = time.time()
            for plugin in self.plugins:
                if now - self.last_tick[plugin.name] >= plugin.interval:
                    try:
                        plugin.tick()
                    except Exception as e:
                        logging.error(f"[{plugin.name}] Error: {e}")
                    self.last_tick[plugin.name] = now
            time.sleep(1)

    def stop(self, signum=None, frame=None):
        self.running = False
        for plugin in self.plugins:
            try:
                plugin.stop()
            except Exception as e:
                logging.error(f"[{plugin.name}] Stop error: {e}")

def load_config() -> dict:
    for path in CONFIG_PATHS:
        if os.path.isfile(path):
            with open(path) as f:
                return json.load(f)
    return {"plugins": {}}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    config = load_config()
    sup = Supervisor(config)
    signal.signal(signal.SIGTERM, sup.stop)
    signal.signal(signal.SIGINT, sup.stop)
    sup.run()
```

- [ ] **Step 2: Create health_reporter plugin**

`packages/vcoo-supervisor/plugins/health_reporter.py`:

```python
import os, json, socket, subprocess, time, urllib.request

class Plugin:
    name = "health_reporter"
    interval = 60

    def start(self, config):
        self.agent_id = os.environ.get("AGENT_ID", config.get("agent_id", ""))
        self.agent_token = os.environ.get("AGENT_TOKEN", config.get("agent_token", ""))
        self.control_plane = os.environ.get("CONTROL_PLANE", config.get("control_plane", "http://localhost:8000"))

    def stop(self):
        pass

    def _get_uptime(self):
        try:
            with open("/proc/uptime") as f:
                return float(f.read().split()[0])
        except:
            return 0

    def _get_disk(self):
        try:
            s = os.statvfs("/")
            total = s.f_frsize * s.f_blocks
            free = s.f_frsize * s.f_bfree
            return total, free, round((1 - free / total) * 100, 1)
        except:
            return 0, 0, 0

    def _hermes_running(self):
        try:
            r = subprocess.run(["pgrep", "-f", "hermes.*gateway"], capture_output=True, timeout=5)
            return r.returncode == 0
        except:
            return False

    def tick(self):
        if not self.agent_id:
            return
        total, free, pct = self._get_disk()
        payload = {
            "hostname": socket.gethostname(),
            "timestamp": time.time(),
            "uptime_seconds": int(self._get_uptime()),
            "hermes_running": self._hermes_running(),
            "disk_total_gb": round(total / (1024**3), 1),
            "disk_free_gb": round(free / (1024**3), 1),
            "disk_used_pct": pct,
            "template_version": os.environ.get("TEMPLATE_VERSION", ""),
            "supervisor_version": "0.1.0",
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.control_plane}/agent/{self.agent_id}/health",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.agent_token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15):
                pass
        except Exception:
            pass
```

- [ ] **Step 3: Create watchdog plugin**

`packages/vcoo-supervisor/plugins/watchdog.py`:

```python
import subprocess, logging

class Plugin:
    name = "watchdog"
    interval = 30

    def start(self, config):
        self.service = config.get("service", "hermes-gateway")
        self.last_restart = 0

    def stop(self):
        pass

    def tick(self):
        try:
            r = subprocess.run(["pgrep", "-f", "hermes.*gateway"], capture_output=True, timeout=5)
            if r.returncode != 0:
                logging.warning("[watchdog] Hermes not running — restarting")
                subprocess.run(["systemctl", "restart", self.service], capture_output=True, timeout=30)
                self.last_restart = __import__("time").time()
        except Exception as e:
            logging.error(f"[watchdog] Error: {e}")
```

- [ ] **Step 4: Create updater plugin**

`packages/vcoo-supervisor/plugins/updater.py`:

```python
import subprocess, logging

class Plugin:
    name = "updater"
    interval = 604800  # 7 days

    def start(self, config):
        pass

    def stop(self):
        pass

    def tick(self):
        try:
            r = subprocess.run(["hermes", "update"], capture_output=True, timeout=120)
            if r.returncode == 0:
                logging.info("[updater] Hermes updated successfully")
            else:
                logging.warning(f"[updater] hermes update failed: {r.stderr.decode()[:200]}")
        except Exception as e:
            logging.error(f"[updater] Error: {e}")
```

- [ ] **Step 5: Create default config**

`packages/vcoo-supervisor/config.json`:

```json
{
  "plugins": {
    "health_reporter": {
      "enabled": true,
      "interval": 60
    },
    "watchdog": {
      "enabled": true,
      "interval": 30,
      "service": "hermes-gateway"
    },
    "updater": {
      "enabled": true,
      "interval": 604800
    }
  }
}
```

- [ ] **Step 6: Create systemd service unit**

`packages/vcoo-supervisor/vcoo-supervisor.service`:

```ini
[Unit]
Description=VCOO Supervisor — Health Reporter + Watchdog
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/vcoo-supervisor/supervisor.py
Restart=on-failure
RestartSec=10
User=ubuntu
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 7: Commit**

```bash
git add packages/vcoo-supervisor/
git commit -m "feat: add vcoo-supervisor — modular Python supervisor with health_reporter, watchdog, updater plugins"
```

---

### Task 7: Rebuild Docker and verify

**Files:**
- None (just commands)

- [ ] **Step 1: Rebuild Docker**

```bash
cd /home/ubuntu/versus/vcoo-onboarding/infra && docker compose build backend && docker compose up -d backend
```

- [ ] **Step 2: Verify endpoints**

```bash
# Create a VCOO
VCOO_ID=$(curl -s http://10.0.0.1:8000/vcoo -X POST -H 'Content-Type: application/json' -d '{"name":"test"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Check audit log is populated
curl -s "http://10.0.0.1:8000/vcoo/$VCOO_ID/audit" | python3 -m json.tool
```

- [ ] **Step 3: Build frontend**

```bash
cd /home/ubuntu/versus/vcoo-onboarding/apps/frontend && npm run build
```
