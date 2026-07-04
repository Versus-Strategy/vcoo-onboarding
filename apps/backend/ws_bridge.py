import asyncio
from fastapi import WebSocket
from typing import Dict

# Simple in-memory bridge: session_id -> websockets
agent_conns: Dict[str, WebSocket] = {}
ui_conns: Dict[str, WebSocket] = {}

lock = asyncio.Lock()

async def register_agent(session_id: str, ws: WebSocket):
    async with lock:
        agent_conns[session_id] = ws

async def unregister_agent(session_id: str):
    async with lock:
        agent_conns.pop(session_id, None)

async def register_ui(session_id: str, ws: WebSocket):
    async with lock:
        ui_conns[session_id] = ws

async def unregister_ui(session_id: str):
    async with lock:
        ui_conns.pop(session_id, None)

async def forward_to_ui(session_id: str, message: str):
    ws = ui_conns.get(session_id)
    if ws:
        await ws.send_text(message)

async def forward_to_agent(session_id: str, message: str):
    ws = agent_conns.get(session_id)
    if ws:
        await ws.send_text(message)
