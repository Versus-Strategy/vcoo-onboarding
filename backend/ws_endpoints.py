# WebSocket endpoints for UI and agents
from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException
from .ws_bridge import register_agent, unregister_agent, register_ui, unregister_ui, forward_to_ui, forward_to_agent
from .auth import verify_operator
from .db import SessionLocal
import json
from . import crud
from sqlalchemy.orm import Session

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def agent_ws(websocket: WebSocket, session_id: str, token: str, db: Session = Depends(get_db)):
    # token is provision token
    await websocket.accept()
    # validate token server-side and mark used atomically
    vcoo_id = crud.validate_provision_token(db, token)
    if not vcoo_id:
        await websocket.close(code=4001)
        return
    # create agent record linked to vcoo
    agent = crud.create_agent(db, vcoo_id=vcoo_id, info='ws-connected')
    await register_agent(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # forward logs to UI and persist
            await forward_to_ui(session_id, data)
            # persist if json and type==log
            try:
                msg = json.loads(data)
                if msg.get('type') == 'log' and 'id' in msg:
                    crud.append_command_log(db, msg.get('id'), msg.get('chunk',''), msg.get('stream','stdout'))
                if msg.get('type') == 'result' and 'id' in msg:
                    crud.mark_command_done(db, msg.get('id'), result=msg.get('summary',''))
            except Exception:
                pass
    except WebSocketDisconnect:
        await unregister_agent(session_id)

async def ui_ws(websocket: WebSocket, session_id: str, operator_token: str = Depends(verify_operator)):
    await websocket.accept()
    await register_ui(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # forward commands to agent
            await forward_to_agent(session_id, data)
    except WebSocketDisconnect:
        await unregister_ui(session_id)
