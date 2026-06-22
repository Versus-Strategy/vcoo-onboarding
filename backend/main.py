from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .db import engine, Base, SessionLocal
from . import models, crud, auth, schemas
from .ws_routes import register_ws_routes
import asyncio
import json
import time

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
    Base.metadata.create_all(bind=engine)
    # register websocket routes
    register_ws_routes(app)

@app.post("/vcoo")
def create_vcoo(db: Session = Depends(get_db)):
    vcoo = crud.create_vcoo(db)
    return {"id": str(vcoo.id)}

@app.get("/vcoo/{vcoo_id}/provision-token")
def get_provision_token(vcoo_id: str, db: Session = Depends(get_db)):
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    # create and store a provision token server-side
    token = crud.create_provision_for_vcoo(db, vcoo_id)
    install_cmd = f"curl -sSL https://example.com/install.sh | PROVISION_TOKEN=*** bash -"
    return {"token": token, "install_command": install_cmd}

@app.post("/register")
def register_agent(payload: dict, db: Session = Depends(get_db)):
    # payload expected: {"token": "..", "info": {"hostname": ".."}}
    token = payload.get("token")
    info = payload.get("info", {})
    # validate token server-side (single-use)
    vcoo_id = crud.validate_provision_token(db, token)
    if not vcoo_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    # create agent record
    agent = crud.create_agent(db, vcoo_id=vcoo_id, info=json.dumps(info))
    # generate agent_token and persist jti
    agent_token = auth.create_agent_token(str(agent.id))
    payload_token = auth.decode_agent_token(agent_token)
    jti = payload_token.get('jti') if payload_token else None
    if jti:
        crud.set_agent_token_jti(db, str(agent.id), jti)
    return {"agent_id": str(agent.id), "vcoo_id": str(vcoo_id), "agent_token": agent_token}

@app.get("/agent/{agent_id}/poll")
def agent_poll(agent_id: str, authorization: str = Header(None), db: Session = Depends(get_db)):
    # Authorization: Bearer ***
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail="missing auth")
    token = authorization.split(None, 1)[1]
    payload = auth.decode_agent_token(token)
    if not payload or payload.get('agent_id') != agent_id:
        raise HTTPException(status_code=401, detail="invalid agent token")
    # update last_seen
    agent = crud.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    crud.touch_agent(db, agent_id)
    # return pending commands for this agent
    pending = crud.get_pending_commands(db, agent_id)
    result = []
    for cmd in pending:
        result.append({"cmd_id": str(cmd.id), "command": cmd.command})
        crud.mark_command_sent(db, cmd.id)
    return {"commands": result}

@app.post("/vcoo/{vcoo_id}/commands")
def enqueue_command(vcoo_id: str, payload: dict, db: Session = Depends(get_db)):
    # payload: {"command": "..."}
    command_text = payload.get("command")
    if not command_text:
        raise HTTPException(status_code=400, detail="command missing")
    # find agent for vcoo
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    if not agent:
        raise HTTPException(status_code=404, detail="no agent connected for vcoo")
    cmd = crud.create_command(db, agent_id=agent.id, command=command_text)
    return {"cmd_id": str(cmd.id)}

@app.post("/vcoo/{vcoo_id}/commands/{cmd_id}/result")
def command_result(vcoo_id: str, cmd_id: str, payload: dict, db: Session = Depends(get_db)):
    # payload: {"status":"done","result":"..."}
    result = payload.get('result', '')
    crud.mark_command_done(db, cmd_id, result=result)
    return {"status": "ok"}


@app.post('/agent/{agent_id}/logs')
def agent_logs(agent_id: str, payload: dict, db: Session = Depends(get_db)):
    # payload: {"cmd_id": "...", "chunk": "...", "stream": "stdout"}
    cmd_id = payload.get('cmd_id')
    chunk = payload.get('chunk', '')
    stream = payload.get('stream', 'stdout')
    if not cmd_id:
        raise HTTPException(status_code=400, detail='cmd_id missing')
    crud.append_command_log(db, cmd_id, chunk, stream)
    return {'status': 'ok'}

@app.get("/vcoo/{vcoo_id}/state")
def get_state(vcoo_id: str, db: Session = Depends(get_db)):
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="Not found")
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    state = v.to_dict()
    state["agent"] = agent.to_dict() if agent else None
    return state
