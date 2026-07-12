# WebSocket endpoints for UI and agents
from fastapi import WebSocket, WebSocketDisconnect
from ws_bridge import register_agent, unregister_agent, register_ui, unregister_ui, forward_to_ui, forward_to_agent
from db import SessionLocal
import json
import crud


async def agent_ws(websocket: WebSocket, session_id: str, token: str):
    """Agent WebSocket — creates its own DB session since not routed through FastAPI DI."""
    db = SessionLocal()
    try:
        await websocket.accept()
        vcoo_id = crud.validate_provision_token(db, token)
        if not vcoo_id:
            await websocket.close(code=4001)
            return
        crud.create_agent(db, vcoo_id=vcoo_id, info='ws-connected')
        await register_agent(session_id, websocket)
        try:
            while True:
                data = await websocket.receive_text()
                await forward_to_ui(session_id, data)
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
    finally:
        db.close()

async def ui_ws(websocket: WebSocket, session_id: str, operator_token: str):
    """Operator UI WebSocket — operator_token already validated by caller."""
    await websocket.accept()
    await register_ui(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await forward_to_agent(session_id, data)
    except WebSocketDisconnect:
        await unregister_ui(session_id)
