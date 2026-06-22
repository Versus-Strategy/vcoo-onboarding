#!/usr/bin/env python3
"""Agent HTTP client (foreground) for polling + logs ingestion.
Usage: python3 agent_http.py <control_plane_base_url> <provision_token>

Behavior:
- POST /register with provision_token -> receive agent_id, vcoo_id, agent_token
- Poll GET /agent/{agent_id}/poll with Authorization: Bearer <agent_token>
- When commands returned, simulate execution and POST logs to /agent/{agent_id}/logs
- Finally POST result to /vcoo/{vcoo_id}/commands/{cmd_id}/result
- Runs in foreground and prints progress
"""
import sys, time, os, requests, uuid
from datetime import datetime

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8000'
PROV = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('PROVISION_TOKEN')

if not PROV:
    print('Provision token required')
    sys.exit(2)

session = requests.Session()

def register():
    resp = session.post(f'{BASE}/register', json={'token': PROV, 'info': {'hostname': os.uname().nodename}})
    if resp.status_code != 200:
        print('register failed', resp.status_code, resp.text)
        return None
    j = resp.json()
    print('Registered agent_id', j.get('agent_id'))
    return j


def poll_loop(agent_id, agent_token, vcoo_id, poll_interval=5):
    headers = {'Authorization': f'Bearer {agent_token}'}
    print('Entering poll loop, agent_id=', agent_id)
    try:
        while True:
            r = session.get(f'{BASE}/agent/{agent_id}/poll', headers=headers, timeout=10)
            if r.status_code == 200:
                j = r.json()
                cmds = j.get('commands', [])
                for c in cmds:
                    cmd_id = c.get('cmd_id')
                    command = c.get('command')
                    print(datetime.utcnow().isoformat(), 'Got command', cmd_id, command)
                    # simulate execution: stream 3 log chunks
                    for i in range(3):
                        chunk = f"simulated output line {i+1} for '{command}'"
                        session.post(f'{BASE}/agent/{agent_id}/logs', json={'cmd_id': cmd_id, 'chunk': chunk, 'stream': 'stdout'})
                        print('sent log chunk')
                        time.sleep(0.5)
                    # post result
                    summary = f"simulated: executed '{command}'"
                    session.post(f'{BASE}/vcoo/{vcoo_id}/commands/{cmd_id}/result', json={'result': summary})
                    print('posted result')
            else:
                print('poll returned', r.status_code, r.text)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print('Interrupted, exiting')


def main():
    meta = register()
    if not meta:
        sys.exit(1)
    agent_id = meta.get('agent_id')
    agent_token = meta.get('agent_token')
    vcoo_id = meta.get('vcoo_id')
    poll_loop(agent_id, agent_token, vcoo_id, poll_interval=5)

if __name__ == '__main__':
    main()
