import sys, os as _os
_sys_path = _os.path.dirname(__file__)
if _sys_path not in sys.path:
    sys.path.insert(0, _sys_path)

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import db
from db import engine, Base, SessionLocal
import models, crud, auth, schemas
from ws_routes import register_ws_routes
import asyncio
import json
import os as _os

app = FastAPI(title="VCOO Onboarding API v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
async def startup():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        import sys as _sys
        print(f"[startup] create_all skipped (DB unreachable): {e}", file=_sys.stderr)
    if _os.getenv("VERCEL_ENV") is None:
        register_ws_routes(app)


# ── Health / Debug ────────────────────────────────────────────

@app.get("/health")
def health():
    import os as _os
    db_url = _os.getenv('POSTGRES_URL', 'NOT SET')
    if '@' in db_url and '://' in db_url:
        parts = db_url.split('@')
        prefix = parts[0].split(':')[0] + ':***'
        masked = prefix + '@' + '@'.join(parts[1:])
    else:
        masked = db_url[:30] + '...'
    return {
        "status": "ok",
        "vercel_env": _os.getenv('VERCEL_ENV', 'NOT SET'),
        "db_host": db_url.split('@')[-1].split('/')[0] if '@' in db_url else 'unknown',
        "db_url_masked": masked,
        "supabase_detected": 'supabase.co' in db_url
    }


# ── Auth ──────────────────────────────────────────────────

@app.post("/auth/verify")
def verify_auth(payload: dict):
    password = payload.get("password", "")
    if auth.verify_dashboard_password(password):
        return {"status": "ok"}
    raise HTTPException(status_code=401, detail="Contraseña incorrecta")

# ── VCOO ──────────────────────────────────────────────────

@app.post("/vcoo")
def create_vcoo(payload: dict = {}, db: Session = Depends(get_db)):
    name = payload.get("name") if payload else None
    modules = payload.get("modules", ["core"]) if payload else ["core"]
    vcoo = crud.create_vcoo(db, name=name)
    # Create onboarding state with selected modules
    crud.get_or_create_onboarding_state(db, str(vcoo.id), modules)
    # Generate provision token
    token = crud.create_provision_for_vcoo(db, str(vcoo.id))
    frontend_url = _os.getenv('FRONTEND_URL', 'https://frontend-ivory-seven-d0aw1wzkae.vercel.app')
    onboarding_url = frontend_url.rstrip('/') + '/setup/' + token
    return {
        "id": str(vcoo.id),
        "name": vcoo.name,
        "status": vcoo.status,
        "modules": modules,
        "onboarding_url": onboarding_url,
    }

@app.get("/vcoos")
def list_vcoos(db: Session = Depends(get_db)):
    """List all VCOOs with agent status and active token."""
    vcoos = crud.list_vcoos(db)
    return [
        {
            "id": str(v.id),
            "name": v.name,
            "status": v.status,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "agent": {
                "id": str(v.agent.id),
                "status": v.agent.status,
                "last_seen": v.agent.last_seen.isoformat() if v.agent.last_seen else None,
            } if v.agent else None,
            "active_token": v.active_token.token if v.active_token else None,
            "token_expires_at": v.active_token.expires_at.isoformat() if v.active_token and v.active_token.expires_at else None,
            "modules": v.modules if hasattr(v, 'modules') and v.modules else ["core"],
        }
        for v in vcoos
    ]


# ── Setup wizard (SPEC v2 §4.2) ───────────────────────────

@app.get("/setup/{token}")
def get_setup_info(token: str, db: Session = Depends(get_db)):
    """Returns onboarding state for the wizard frontend.
    Read-only — does not consume the token."""
    vcoo_id = crud.lookup_provision_token(db, token)
    if not vcoo_id:
        raise HTTPException(status_code=404, detail="Token invalido o expirado")
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    st = crud.get_onboarding_state(db, vcoo_id)
    if not st:
        raise HTTPException(status_code=404, detail="No hay datos de onboarding")
    from onboarding import get_total_steps
    modules = list(st.modules or ["core"])
    total = get_total_steps(modules)
    done = len(st.completed or [])
    frontend_url = _os.getenv('FRONTEND_URL', 'https://vcoo-onboarding.vercel.app')
    install_cmd = f"curl -sSL {frontend_url}/install.sh | PROVISION_TOKEN={token} bash -"
    return {
        "vcoo_id": str(v.id),
        "name": v.name,
        "modules": modules,
        "step": st.step,
        "status": st.status,
        "completed": st.completed or [],
        "errors": st.errors or [],
        "retry_count": st.retry_count or {},
        "progress": {"total": total, "done": done},
        "install_command": install_cmd,
    }


@app.post("/setup/{token}/verify")
def trigger_step_verification(token: str, db: Session = Depends(get_db)):
    """Client clicks 'Verificar' in the wizard — enqueues the verification command.
    If no agent is connected, auto-advances the step for dev/demo mode."""
    vcoo_id = crud.lookup_provision_token(db, token)
    if not vcoo_id:
        raise HTTPException(status_code=404, detail="Token invalido o expirado")
    st = crud.get_onboarding_state(db, vcoo_id)
    if not st:
        raise HTTPException(status_code=404, detail="No hay datos de onboarding")
    from onboarding import get_step_command
    step = st.step
    if step == "finalize" or step == "done":
        return {"status": "skip", "message": "Onboarding ya completado"}
    cmd_name = get_step_command(step)

    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    # Check if agent is active (seen within last 2 minutes)
    agent_alive = False
    if agent and agent.last_seen:
        import datetime as dt
        ago = (dt.datetime.utcnow() - agent.last_seen.replace(tzinfo=None)).total_seconds()
        agent_alive = ago < 120

    if agent and agent_alive:
        # Real agent connected — enqueue the command
        cmd = crud.create_command(db, agent_id=str(agent.id), command=cmd_name, step=step)
        return {
            "status": "enqueued",
            "cmd_id": str(cmd.id),
            "step": step,
            "command": cmd_name,
        }
    else:
        # Dev/demo mode — auto-advance the step
        crud.advance_onboarding_step(db, vcoo_id, step)
        db.refresh(st)
        return {
            "status": "auto_completed",
            "step": step,
            "next_step": st.step,
            "message": "Paso completado automaticamente (modo demo). En produccion, el agente ejecutara la verificacion real.",
        }


@app.get("/vcoo/{vcoo_id}/provision-token")
def get_provision_token(vcoo_id: str, db: Session = Depends(get_db)):
    """Return existing active token for this VCOO, or create one if none exists."""
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    active = crud.get_active_token_for_vcoo(db, vcoo_id)
    if active:
        token = active.token
    else:
        token = crud.create_provision_for_vcoo(db, vcoo_id)
    frontend_url = _os.getenv('FRONTEND_URL', 'https://vcoo-onboarding.vercel.app')
    install_cmd = f"curl -sSL {frontend_url}/install.sh | PROVISION_TOKEN={token} bash -"
    return {"token": token, "install_command": install_cmd}

@app.post("/vcoo/{vcoo_id}/regenerate-token")
def regenerate_token(vcoo_id: str, db: Session = Depends(get_db)):
    """Revoke current token and generate a new one."""
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    token = crud.regenerate_token_for_vcoo(db, vcoo_id)
    frontend_url = _os.getenv('FRONTEND_URL', 'https://vcoo-onboarding.vercel.app')
    install_cmd = f"curl -sSL {frontend_url}/install.sh | PROVISION_TOKEN={token} bash -"
    return {"token": token, "install_command": install_cmd}

@app.post("/vcoo/{vcoo_id}/complete")
def complete_vcoo(vcoo_id: str, db: Session = Depends(get_db)):
    """Mark VCOO as completed (setup finished). Logs are preserved."""
    v = crud.complete_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    return {"status": "completed"}

@app.post("/vcoo/{vcoo_id}/reactivate")
def reactivate_vcoo(vcoo_id: str, db: Session = Depends(get_db)):
    """Reactivate a completed VCOO and generate a new token."""
    token = crud.reactivate_vcoo(db, vcoo_id)
    if not token:
        raise HTTPException(status_code=404, detail="VCOO not found")
    frontend_url = _os.getenv('FRONTEND_URL', 'https://vcoo-onboarding.vercel.app')
    install_cmd = f"curl -sSL {frontend_url}/install.sh | PROVISION_TOKEN={token} bash -"
    return {"status": "active", "token": token, "install_command": install_cmd}

@app.delete("/vcoo/{vcoo_id}")
def delete_vcoo(vcoo_id: str, db: Session = Depends(get_db)):
    """Permanently delete a VCOO and all associated data."""
    ok = crud.delete_vcoo(db, vcoo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="VCOO not found")
    return {"status": "deleted"}


# ── Agent registration & auth ─────────────────────────────

@app.post("/register")
def register_agent(payload: dict, db: Session = Depends(get_db)):
    token = payload.get("token")
    info = payload.get("info", {})
    vcoo_id = crud.validate_provision_token(db, token)
    if not vcoo_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    agent = crud.create_agent(db, vcoo_id=vcoo_id, info=json.dumps(info))
    agent_token = auth.create_agent_token(str(agent.id))
    payload_token = auth.decode_agent_token(agent_token)
    jti = payload_token.get('jti') if payload_token else None
    if jti:
        crud.set_agent_token_jti(db, str(agent.id), jti)
    return {"agent_id": str(agent.id), "vcoo_id": str(vcoo_id), "agent_token": agent_token}


# ── Agent polling & logs ──────────────────────────────────

@app.get("/agent/{agent_id}/poll")
def agent_poll(agent_id: str, authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail="missing auth")
    token = authorization.split(None, 1)[1]
    payload = auth.decode_agent_token(token)
    if not payload or payload.get('agent_id') != agent_id:
        raise HTTPException(status_code=401, detail="invalid agent token")
    agent = crud.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    crud.touch_agent(db, agent_id)
    pending = crud.get_pending_commands(db, agent_id)
    # Solo servir comandos validos del COMMAND_MAP
    VALID_COMMANDS = {
        "verify-bootstrap", "verify-google", "verify-trello", "verify-email",
        "verify-github", "verify-vercel", "verify-supabase",
        "save-creds", "finalize",
    }
    result = []
    for cmd in pending:
        if cmd.command not in VALID_COMMANDS:
            crud.mark_command_done(db, cmd.id, result="BLOCKED: comando no reconocido, descartado")
            continue
        result.append({"cmd_id": str(cmd.id), "command": cmd.command, "step": cmd.step})
        crud.mark_command_sent(db, cmd.id)

    # Incluir progreso del onboarding para la TUI
    progress_data = {}
    if agent.vcoo_id:
        st = crud.get_onboarding_state(db, str(agent.vcoo_id))
        if st:
            from onboarding import get_total_steps
            modules = list(st.modules or ["core"])
            progress_data = {
                "done": len(st.completed or []),
                "total": get_total_steps(modules),
            }
    return {
        "commands": result,
        "progress": progress_data,
        "step": st.step if agent.vcoo_id and (st := crud.get_onboarding_state(db, str(agent.vcoo_id))) else "",
    }

@app.post("/agent/{agent_id}/complete")
def agent_setup_complete(agent_id: str, db: Session = Depends(get_db)):
    """Agent calls this when onboarding setup finishes.
    Marks the VCOO as completed and revokes its token."""
    agent = crud.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    crud.complete_vcoo(db, str(agent.vcoo_id))
    return {"status": "ok", "vcoo_completed": True}

@app.post('/agent/{agent_id}/logs')
def agent_logs(agent_id: str, payload: dict, db: Session = Depends(get_db)):
    cmd_id = payload.get('cmd_id')
    chunk = payload.get('chunk', '')
    stream = payload.get('stream', 'stdout')
    if not cmd_id:
        raise HTTPException(status_code=400, detail='cmd_id missing')
    crud.append_command_log(db, cmd_id, chunk, stream)
    return {'status': 'ok'}

@app.get('/agent/{agent_id}/logs')
def get_command_logs(agent_id: str, cmd_id: str = "", db: Session = Depends(get_db)):
    """Retrieve command logs for a specific cmd_id (or all recent)."""
    if cmd_id:
        logs = crud.get_command_logs(db, cmd_id)
        return {"cmd_id": cmd_id, "logs": logs}
    # If no cmd_id, return recent commands with their logs for this agent
    commands = crud.get_agent_commands(db, agent_id, limit=20)
    result = []
    for cmd in commands:
        logs = crud.get_command_logs(db, str(cmd.id))
        result.append({
            "cmd_id": str(cmd.id),
            "command": cmd.command,
            "step": cmd.step,
            "status": cmd.status,
            "result": cmd.result[:500] if cmd.result else "",
            "logs": logs[-50:] if logs else [],
        })
    return {"commands": result}


# ── Commands ──────────────────────────────────────────────

@app.post("/vcoo/{vcoo_id}/commands")
def enqueue_command(vcoo_id: str, payload: dict, db: Session = Depends(get_db)):
    command_text = payload.get("command")
    if not command_text:
        raise HTTPException(status_code=400, detail="command missing")
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    if not agent:
        raise HTTPException(status_code=404, detail="no agent connected for vcoo")
    step = payload.get("step")
    cmd = crud.create_command(db, agent_id=agent.id, command=command_text, step=step)
    return {"cmd_id": str(cmd.id)}

@app.post("/vcoo/{vcoo_id}/commands/{cmd_id}/result")
def command_result(vcoo_id: str, cmd_id: str, payload: dict, db: Session = Depends(get_db)):
    result = payload.get('result', '')
    crud.mark_command_done(db, cmd_id, result=result)
    return {"status": "ok"}


# ── State ─────────────────────────────────────────────────

@app.get("/vcoo/{vcoo_id}/state")
def get_state(vcoo_id: str, db: Session = Depends(get_db)):
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="Not found")
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    state = v.to_dict()
    state["agent"] = agent.to_dict() if agent else None
    active_token = crud.get_active_token_for_vcoo(db, vcoo_id)
    state["active_token"] = active_token.token if active_token else None
    # Add onboarding state (SPEC v2)
    st = crud.get_onboarding_state(db, vcoo_id)
    if st:
        from onboarding import get_total_steps
        modules = list(st.modules or ["core"])
        state["modules"] = modules
        state["step"] = st.step
        state["onboarding_status"] = st.status
        state["completed_steps"] = st.completed or []
        state["onboarding_errors"] = st.errors or []
        state["retry_count"] = st.retry_count or {}
        state["progress"] = {
            "total": get_total_steps(modules),
            "done": len(st.completed or []),
        }
    return state


# ── Agent result (SPEC v2 §4.4) ──────────────────────────

@app.post("/agent/{agent_id}/result")
def agent_report_result(agent_id: str, payload: dict, db: Session = Depends(get_db)):
    """Agent reports command result. ACK semantics with backoff support."""
    from fastapi.responses import JSONResponse
    cmd_id = payload.get("cmd_id")
    step = payload.get("step", "")
    status = payload.get("status", "ok")
    output = payload.get("output", "")
    if not cmd_id:
        raise HTTPException(status_code=400, detail="cmd_id missing")
    cmd, acked, next_step, status_code = crud.process_agent_result(
        db, agent_id, cmd_id, step, status, output
    )
    if status_code == 404:
        raise HTTPException(status_code=404, detail="Command not found")
    if status_code == 409:
        return JSONResponse(
            content={"ack": True, "cmd_id": cmd_id, "status": "already_reported"},
            status_code=409,
        )
    result = {"ack": True, "cmd_id": cmd_id}
    if next_step:
        result["next_step"] = next_step
    if hasattr(cmd, 'id'):
        result["cmd_id"] = str(cmd.id)
    return JSONResponse(content=result, status_code=status_code)


# ── Agent heartbeat (SPEC v2 §4.6) ───────────────────────

@app.post("/agent/heartbeat")
def agent_heartbeat_endpoint(payload: dict, db: Session = Depends(get_db)):
    agent_id = payload.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id missing")
    crud.agent_heartbeat(db, agent_id)
    return {"ack": True}


# ── Onboarding management (operator actions) ─────────────

@app.post("/vcoo/{vcoo_id}/onboarding/retry")
def retry_onboarding_step(vcoo_id: str, payload: dict, db: Session = Depends(get_db)):
    """Operator manually retries a blocked/failed step."""
    step = payload.get("step")
    if not step:
        raise HTTPException(status_code=400, detail="step missing")
    st = crud.reset_onboarding_retry(db, vcoo_id, step)
    if not st:
        raise HTTPException(status_code=404, detail="Not found")
    # Re-enqueue the verification command
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    if agent:
        from onboarding import get_step_command
        cmd_name = get_step_command(step)
        crud.create_command(db, agent_id=str(agent.id), command=cmd_name, step=step)
    return {"status": "ok", "step": step, "onboarding_status": st.status}


@app.post("/vcoo/{vcoo_id}/onboarding/skip")
def skip_onboarding_step(vcoo_id: str, payload: dict, db: Session = Depends(get_db)):
    """Operator skips a blocked/impossible step."""
    step = payload.get("step")
    if not step:
        raise HTTPException(status_code=400, detail="step missing")
    st = crud.skip_onboarding_step(db, vcoo_id, step)
    if not st:
        raise HTTPException(status_code=404, detail="Not found")
    return {"status": "ok", "step": step, "next_step": st.step}


# ── Playbooks ──────────────────────────────────────────────

_PLAYBOOKS_DIR = _os.path.join(_os.path.dirname(__file__), 'playbooks')

@app.get('/playbooks')
def list_playbooks():
    if not _os.path.isdir(_PLAYBOOKS_DIR):
        return {'playbooks': []}
    names = sorted(
        f for f in _os.listdir(_PLAYBOOKS_DIR)
        if _os.path.isfile(_os.path.join(_PLAYBOOKS_DIR, f)) and not f.startswith('.')
    )
    return {'playbooks': names}

@app.get('/playbooks/{name}')
def get_playbook(name: str):
    path = _os.path.join(_PLAYBOOKS_DIR, name)
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Playbook not found')
    content = open(path).read()
    return {'name': name, 'script': content}

@app.get('/playbooks/{name}/raw')
def get_playbook_raw(name: str):
    """Returns raw script content (for curl downloads from install.sh)."""
    from fastapi.responses import PlainTextResponse
    path = _os.path.join(_PLAYBOOKS_DIR, name)
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Playbook not found')
    content = open(path).read()
    return PlainTextResponse(content, media_type='text/x-python')


# ── Static assets ─────────────────────────────────────────

_STATIC_DIR = _os.path.join(_os.path.dirname(__file__))

@app.get('/install.sh')
def get_install_script():
    path = _os.path.join(_STATIC_DIR, 'install.sh')
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Not found')
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(open(path).read(), media_type='text/x-sh')

@app.get('/agent_http.py')
def get_agent_script():
    path = _os.path.join(_STATIC_DIR, 'agent_http.py')
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Not found')
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(open(path).read(), media_type='text/x-python')
