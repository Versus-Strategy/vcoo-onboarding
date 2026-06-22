from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .db import engine, Base, SessionLocal
from . import models, crud, auth
import asyncio
import json

app = FastAPI(title="VCOO Onboarding API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory registry of connected websockets: agent_id -> websocket
connected_agents = {}
connected_agents_lock = asyncio.Lock()

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

@app.post("/vcoo")
def create_vcoo(db: Session = Depends(get_db)):
    vcoo = crud.create_vcoo(db)
    return {"id": str(vcoo.id)}

@app.get("/vcoo/{vcoo_id}/provision-token")
def get_provision_token(vcoo_id: str, db: Session = Depends(get_db)):
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    token = auth.create_provision_token(vcoo_id)
    # Provide a sample one-liner for the customer
    install_cmd = f"docker run -e PROVISION_TOKEN={token} --rm vcoo-agent:latest"
    return {"token": token, "install_command": install_cmd}

@app.post("/register")
def register_agent(payload: dict, db: Session = Depends(get_db)):
    # payload expected: {"token": "..", "info": {"hostname": ".."}}
    token = payload.get("token")
    info = payload.get("info", {})
    data = auth.decode_provision_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    vcoo_id = data.get("vcoo_id")
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    agent = crud.create_agent(db, vcoo_id=vcoo_id, info=json.dumps(info))
    # return ws url and agent id
    ws_url = f"/ws/{agent.id}"
    return {"agent_id": str(agent.id), "ws_url": ws_url}

@app.websocket("/ws/{agent_id}")
async def agent_ws(websocket: WebSocket, agent_id: str):
    await websocket.accept()
    try:
        # simple auth can be extended: token query param or header
        async with connected_agents_lock:
            connected_agents[agent_id] = websocket
        # send pending commands
        db = SessionLocal()
        try:
            pending = crud.get_pending_commands(db, agent_id)
            for cmd in pending:
                await websocket.send_text(json.dumps({"cmd_id": str(cmd.id), "command": cmd.command}))
                crud.mark_command_sent(db, cmd.id)
        finally:
            db.close()

        while True:
            data = await websocket.receive_text()
            # agent can send status updates
            try:
                msg = json.loads(data)
            except Exception:
                msg = {"raw": data}
            print(f"Received from agent {agent_id}: {msg}")

    except WebSocketDisconnect:
        print(f"Agent {agent_id} disconnected")
    finally:
        async with connected_agents_lock:
            if agent_id in connected_agents:
                del connected_agents[agent_id]

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
    # if agent websocket connected, send immediately
    async def send_now():
        async with connected_agents_lock:
            ws = connected_agents.get(str(agent.id))
            if ws:
                try:
                    await ws.send_text(json.dumps({"cmd_id": str(cmd.id), "command": cmd.command}))
                    crud.mark_command_sent(db, cmd.id)
                except Exception as e:
                    print("Failed to send to agent", e)
    asyncio.create_task(send_now())
    return {"cmd_id": str(cmd.id)}

@app.get("/vcoo/{vcoo_id}/state")
def get_state(vcoo_id: str, db: Session = Depends(get_db)):
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="Not found")
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    state = v.to_dict()
    state["agent"] = agent.to_dict() if agent else None
    return state
