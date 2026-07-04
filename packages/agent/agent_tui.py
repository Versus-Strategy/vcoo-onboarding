#!/usr/bin/env python3
"""
Agent TUI client with command handling.
Usage: python3 agent_tui.py ws://localhost:8000 <session_id> <token>

Behaviors implemented:
- Connect to control-plane websocket endpoint /agent-ws/{session_id}?token={token}
- Listen for messages. If message.type == 'cmd' -> simulate execution:
    - send 'log' messages for stdout
    - send 'result' message when done
- Send heartbeat periodically
- Use rich for nicer console output
"""
import asyncio
import sys
import json
from rich.console import Console
from websockets import connect

console = Console()

async def handle_cmd(ws, data):
    cmd_id = data.get('id')
    command = data.get('command')
    console.print(f"[yellow]Received command {cmd_id}: {command}")
    # Simulate streaming logs
    for i in range(3):
        chunk = f"simulated output line {i+1} for '{command}'"
        await ws.send(json.dumps({'type':'log','id':cmd_id,'chunk':chunk,'stream':'stdout'}))
        await asyncio.sleep(0.5)
    # Send final result
    summary = f"simulated: executed '{command}'"
    await ws.send(json.dumps({'type':'result','id':cmd_id,'summary':summary,'exit_code':0}))
    console.print(f"[green]Command {cmd_id} done")

async def run(ws_url, session_id, token):
    uri = f"{ws_url}/agent-ws/{session_id}?token={token}"
    console.print(f"Connecting to {uri}")
    async with connect(uri) as ws:
        console.print(f"[green]Connected to control-plane as agent for session {session_id}")

        async def receiver():
            try:
                async for msg in ws:
                    try:
                        data = json.loads(msg)
                    except Exception:
                        console.print(f"[red]Received non-json: {msg}")
                        continue
                    t = data.get('type')
                    if t == 'log':
                        console.print(f"[blue][LOG][/blue] {data.get('chunk','')}")
                    elif t == 'cmd':
                        await handle_cmd(ws, data)
                    elif t == 'close':
                        console.print('[bold red]Session closed by server')
                        return
                    else:
                        console.print(f"[magenta]Unknown message type: {t} -- {data}")
            except asyncio.CancelledError:
                return

        async def sender():
            while True:
                await asyncio.sleep(10)
                try:
                    await ws.send(json.dumps({'type':'heartbeat'}))
                except Exception:
                    return

        await asyncio.gather(receiver(), sender())

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print('usage: agent_tui.py <ws_url> <session_id> <token>')
        sys.exit(1)
    ws_url = sys.argv[1]
    session_id = sys.argv[2]
    token = sys.argv[3]
    asyncio.run(run(ws_url, session_id, token))
