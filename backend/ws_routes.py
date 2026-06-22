from fastapi import WebSocket
from ws_endpoints import agent_ws, ui_ws
import auth


def register_ws_routes(app):
    @app.websocket('/agent-ws/{session_id}')
    async def _agent_ws(websocket: WebSocket, session_id: str):
        # agent passes token as query param: ?token=...
        token = websocket.query_params.get('token')
        await agent_ws(websocket, session_id, token)

    @app.websocket('/setup-ws/{session_id}')
    async def _ui_ws(websocket: WebSocket, session_id: str):
        # operator can pass op_token as query param: ?op_token=...
        op_token = websocket.query_params.get('op_token')
        # validate operator token using auth.verify_operator (which expects an Authorization header)
        auth_header = f"Bearer {op_token}" if op_token else None
        try:
            # this will raise HTTPException if invalid
            auth.verify_operator(auth_header)
        except Exception:
            # reject connection
            await websocket.close(code=1008)
            return
        await ui_ws(websocket, session_id, op_token)
