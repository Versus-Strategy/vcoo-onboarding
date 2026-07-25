#!/usr/bin/env python3
"""vcoo-agent: Standalone agent (polling POC)

Behavior:
- Read PROVISION_TOKEN from env or arg
- POST /register to control plane (http://localhost:8000/register) if no agent.token
- Receive {agent_id, vcoo_id, agent_token}
- Store agent_token encrypted with MASTER_KEY in storage_dir (prefers /etc/vcoo-agent, otherwise ./.vcoo-agent)
- Poll GET /agent/{agent_id}/poll every 15s with Authorization: Bearer <agent_token>
- On receiving commands, simulate execution and POST result to /vcoo/{vcoo_id}/commands/{cmd_id}/result

TODO: execution sandboxing, TLS (wss/httpS), token rotation, robust error handling
"""
import os
import sys
import time
import json
import platform
import asyncio
import logging
import random
from typing import Optional

from cryptography.fernet import Fernet
import httpx

logging.basicConfig(level=logging.INFO, format='[vcoo-agent] %(message)s')

CONTROL_PLANE = os.getenv('CONTROL_PLANE_URL', 'http://localhost:8000')
PROVISION_TOKEN = os.getenv('PROVISION_TOKEN')
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '15'))

# storage dir: prefer /etc/vcoo-agent for real installs, fallback to local ./.vcoo-agent for testing
if os.path.isdir('/etc/vcoo-agent'):
    STORAGE_DIR = '/etc/vcoo-agent'
else:
    STORAGE_DIR = os.path.join(os.getcwd(), '.vcoo-agent')

MASTER_KEY_PATH = os.path.join(STORAGE_DIR, 'master.key')
AGENT_TOKEN_PATH = os.path.join(STORAGE_DIR, 'agent.token')
AGENT_META_PATH = os.path.join(STORAGE_DIR, 'agent.json')

os.makedirs(STORAGE_DIR, exist_ok=True)


def ensure_master_key():
    if not os.path.exists(MASTER_KEY_PATH):
        key = Fernet.generate_key().decode()
        with open(MASTER_KEY_PATH, 'w') as f:
            f.write(key)
        try:
            os.chmod(MASTER_KEY_PATH, 0o600)
        except Exception:
            pass
    with open(MASTER_KEY_PATH, 'r') as f:
        return f.read().strip()


MASTER_KEY = ensure_master_key()
fernet = Fernet(MASTER_KEY.encode())


def encrypt_token(token: str) -> str:
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(enc: str) -> str:
    return fernet.decrypt(enc.encode()).decode()


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


def save_agent_token(agent_id: str, agent_token: str, vcoo_id: str):
    enc = encrypt_token(agent_token)
    with open(AGENT_TOKEN_PATH, 'w') as f:
        f.write(enc)
    with open(AGENT_META_PATH, 'w') as f:
        json.dump({'agent_id': agent_id, 'vcoo_id': vcoo_id}, f)
    try:
        os.chmod(AGENT_TOKEN_PATH, 0o600)
        os.chmod(AGENT_META_PATH, 0o600)
    except Exception:
        pass


def load_agent():
    if not os.path.exists(AGENT_TOKEN_PATH) or not os.path.exists(AGENT_META_PATH):
        return None
    with open(AGENT_TOKEN_PATH, 'r') as f:
        enc = f.read().strip()
    token = decrypt_token(enc)
    with open(AGENT_META_PATH, 'r') as f:
        meta = json.load(f)
    return {'agent_token': token, 'agent_id': meta.get('agent_id'), 'vcoo_id': meta.get('vcoo_id')}


async def poll_loop(agent_id: str, agent_token: str, vcoo_id: str):
    headers = {'Authorization': f'Bearer {agent_token}'}
    poll_url = f"{CONTROL_PLANE}/agent/{agent_id}/poll"
    logging.info(f"Entering poll loop for agent {agent_id} (vcoo {vcoo_id}), interval {POLL_INTERVAL}s")
    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            try:
                r = await client.get(poll_url, headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    commands = data.get('commands', [])
                    if commands:
                        logging.info(f"Received {len(commands)} commands")
                        for cmd in commands:
                            cmd_id = cmd.get('cmd_id')
                            command = cmd.get('command')
                            logging.info(f"[CMD] id={cmd_id} command={command}")
                            # Simulate execution
                            result = f"simulated: executed '{command}'"
                            # Report result
                            try:
                                res_url = f"{CONTROL_PLANE}/agent/{agent_id}/result"
                                resp = await client.post(res_url, json={'cmd_id': cmd_id, 'status': 'ok', 'output': result})
                                logging.info(f"Reported result for {cmd_id}: {resp.status_code}")
                            except Exception as e:
                                logging.error(f"Failed to post result: {e}")
                    else:
                        logging.debug("No commands")
                else:
                    logging.error(f"Poll returned status {r.status_code}: {r.text}")
            except Exception as e:
                logging.error(f"Poll error: {e}")
            # jitter
            jitter = random.uniform(0, 2)
            await asyncio.sleep(POLL_INTERVAL + jitter)


async def main():
    # Load existing agent token
    loaded = load_agent()
    if loaded:
        agent_token = loaded['agent_token']
        agent_id = loaded['agent_id']
        vcoo_id = loaded['vcoo_id']
        logging.info(f"Found existing agent {agent_id} for vcoo {vcoo_id}")
    else:
        provision = PROVISION_TOKEN
        if not provision and len(sys.argv) > 1:
            provision = sys.argv[1]
        if not provision:
            logging.error("PROVISION_TOKEN not provided. Set env PROVISION_TOKEN or pass as first arg.")
            return 2
        reg = await register(provision)
        if not reg:
            logging.error("Registration failed; aborting")
            return 3
        agent_id = reg.get('agent_id')
        vcoo_id = reg.get('vcoo_id')
        agent_token = reg.get('agent_token')
        if not agent_id or not agent_token:
            logging.error("Bad register response")
            return 4
        save_agent_token(agent_id, agent_token, vcoo_id)
        logging.info(f"Registered agent_id={agent_id} vcoo_id={vcoo_id}")
    await poll_loop(agent_id, agent_token, vcoo_id)
    return 0


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info('Interrupted')
