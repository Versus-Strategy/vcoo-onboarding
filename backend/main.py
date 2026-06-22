from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .db import engine, Base, SessionLocal
from . import models, crud, auth, schemas
from .ws_routes import register_ws_routes
import asyncio
import json
import os as _os

app = FastAPI(title="VCOO Onboarding API")

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
        # In serverless, DB may not be reachable on cold start — tables should be pre-created
        import sys as _sys
        print(f"[startup] create_all skipped (DB unreachable): {e}", file=_sys.stderr)
    # WebSocket routes only in dev (Vercel serverless does not support WS)
    if _os.getenv("VERCEL_ENV") is None:
        register_ws_routes(app)


# ── Health / Debug ────────────────────────────────────────────

@app.get("/health")
def health():
    """Debug endpoint: show DB connection status (no secrets)."""
    import os as _os
    db_url = _os.getenv('POSTGRES_URL', 'NOT SET')
    # Mask password for safety
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


# ── VCOO ──────────────────────────────────────────────────

@app.post("/vcoo")
def create_vcoo(db: Session = Depends(get_db)):
    vcoo = crud.create_vcoo(db)
    return {"id": str(vcoo.id)}

@app.get("/vcoos")
def list_vcoos(db: Session = Depends(get_db)):
    """List all VCOOs with agent status."""
    vcoos = crud.list_vcoos(db)
    return [
        {
            "id": str(v.id),
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "agent": {
                "id": str(v.agent.id),
                "status": v.agent.status,
                "last_seen": v.agent.last_seen.isoformat() if v.agent.last_seen else None,
            } if v.agent else None,
        }
        for v in vcoos
    ]

@app.get("/vcoo/{vcoo_id}/provision-token")
def get_provision_token(vcoo_id: str, db: Session = Depends(get_db)):
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    token = crud.create_provision_for_vcoo(db, vcoo_id)
    frontend_url = _os.getenv('FRONTEND_URL', 'https://vcoo-onboarding.vercel.app')
    install_cmd = f"curl -sSL {frontend_url}/install.sh | PROVISION_TOKEN={token} bash -"
    return {"token": token, "install_command": install_cmd}


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
    result = []
    for cmd in pending:
        result.append({"cmd_id": str(cmd.id), "command": cmd.command})
        crud.mark_command_sent(db, cmd.id)
    return {"commands": result}

@app.post('/agent/{agent_id}/logs')
def agent_logs(agent_id: str, payload: dict, db: Session = Depends(get_db)):
    cmd_id = payload.get('cmd_id')
    chunk = payload.get('chunk', '')
    stream = payload.get('stream', 'stdout')
    if not cmd_id:
        raise HTTPException(status_code=400, detail='cmd_id missing')
    crud.append_command_log(db, cmd_id, chunk, stream)
    return {'status': 'ok'}


# ── Commands ──────────────────────────────────────────────

@app.post("/vcoo/{vcoo_id}/commands")
def enqueue_command(vcoo_id: str, payload: dict, db: Session = Depends(get_db)):
    command_text = payload.get("command")
    if not command_text:
        raise HTTPException(status_code=400, detail="command missing")
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    if not agent:
        raise HTTPException(status_code=404, detail="no agent connected for vcoo")
    cmd = crud.create_command(db, agent_id=agent.id, command=command_text)
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
    return state


# ── Playbooks ──────────────────────────────────────────────

_PLAYBOOKS_DIR = _os.path.join(_os.path.dirname(__file__), 'playbooks')


@app.get('/playbooks')
def list_playbooks():
    """List available playbook names (safe scripts for agent execution)."""
    if not _os.path.isdir(_PLAYBOOKS_DIR):
        return {'playbooks': []}
    names = sorted(
        f for f in _os.listdir(_PLAYBOOKS_DIR)
        if _os.path.isfile(_os.path.join(_PLAYBOOKS_DIR, f)) and not f.startswith('.')
    )
    return {'playbooks': names}


@app.get('/playbooks/{name}')
def get_playbook(name: str):
    """Return a playbook script by name. Agents download and execute these."""
    path = _os.path.join(_PLAYBOOKS_DIR, name)
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Playbook not found')
    content = open(path).read()
    return {'name': name, 'script': content}


# ── Static assets (served alongside API) ──────────────────

_STATIC_DIR = _os.path.join(_os.path.dirname(__file__))

_STATIC_FILES = {
    'install.sh': 'text/x-sh',
    'agent_http.py': 'text/x-python',
}


@app.get('/install.sh')
def get_install_script():
    """Serve the agent one-liner installer."""
    path = _os.path.join(_STATIC_DIR, 'install.sh')
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Not found')
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(open(path).read(), media_type='text/x-sh')


@app.get('/agent_http.py')
def get_agent_script():
    """Serve the agent Python script."""
    path = _os.path.join(_STATIC_DIR, 'agent_http.py')
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Not found')
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(open(path).read(), media_type='text/x-python')
