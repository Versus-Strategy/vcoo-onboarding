#!/usr/bin/env python3
"""vcoo-agent: Standalone agent (POC)

Behavior:
- Read PROVISION_TOKEN from env or arg
- POST /register to control plane (http://localhost:8000/register)
- Receive {agent_id, ws_url}
- Connect to ws_url via websocket and listen for JSON messages {cmd_id, command}
- On command: print, send ack back via websocket

TODO: execution sandboxing, TLS (wss), token validation, persistent storage, proper error handling
"""
import os
import sys
import time
import json
import platform
import asyncio
import logging
from typing import Optional

import httpx
import websockets

logging.basicConfig(level=logging.INFO, format='[vcoo-agent] %(message)s')

CONTROL_PLANE = os.getenv('CONTROL_PLANE_URL', 'http://localhost:8000')
PROVISION_TOKEN = os.getenv('PROVISION_TOKEN')

async def register(provision_token: str) -> Optional[dict]:
    url = f"{CONTROL_PLANE}/register"
    info = {"hostname": platform.node(), "os": platform.system(), "py_version": sys.version}
    payload = {"token": provision_token, "info": info}
    logging.info(f"Registering with control plane {url} ...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logging.error(f"Register failed: {e}")
        return None

async def run_ws(ws_url: str, agent_id: str):
    logging.info(f"Connecting to websocket {ws_url} as agent {agent_id}")
    try:
        async with websockets.connect(ws_url) as websocket:
            logging.info("Websocket connected, listening for commands...")
            async for message in websocket:
                try:
                    msg = json.loads(message)
                except Exception:
                    logging.info(f"Received raw: {message}")
                    continue
                logging.info(f"Received message: {msg}")
                cmd_id = msg.get('cmd_id')
                command = msg.get('command')
                # For POC we don't execute commands. We only log and ack.
                logging.info(f"[CMD] id={cmd_id} command={command}")
                ack = {"cmd_id": cmd_id, "status": "received", "agent_id": agent_id}
                await websocket.send(json.dumps(ack))
    except Exception as e:
        logging.error(f"Websocket error: {e}")

async def main():
    provision = PROVISION_TOKEN
    if not provision:
        if len(sys.argv) > 1:
            provision = sys.argv[1]
    if not provision:
        logging.error("PROVISION_TOKEN not provided. Set env PROVISION_TOKEN or pass as first arg.")
        return 2
    reg = await register(provision)
    if not reg:
        logging.error("Registration failed; aborting")
        return 3
    agent_id = reg.get('agent_id')
    ws_url = reg.get('ws_url')
    # ws_url may be relative like /ws/<id>; convert to ws://
    if ws_url.startswith('/'):
        # derive from CONTROL_PLANE
        base = CONTROL_PLANE.replace('http://', 'ws://').replace('https://', 'wss://')
        ws_url = base.rstrip('/') + ws_url
    logging.info(f"Registered agent_id={agent_id} ws_url={ws_url}")
    # Connect and run
    await run_ws(ws_url, agent_id)
    return 0

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info('Interrupted')
