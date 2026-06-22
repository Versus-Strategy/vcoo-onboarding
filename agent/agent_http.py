#!/usr/bin/env python3
"""Agent HTTP client (foreground) — polling + real execution + logs ingestion.

Usage: python3 agent_http.py <control_plane_base_url> <provision_token>

Features:
- POST /register with provision_token -> receive agent_id, vcoo_id, agent_token
- Poll GET /agent/{agent_id}/poll every 5s (configurable via env)
- Execute received commands with sandbox (timeout, drop-privileges, whitelist)
- Stream stdout/stderr lines to POST /agent/{agent_id}/logs
- POST final result to /vcoo/{vcoo_id}/commands/{cmd_id}/result
- Runs in foreground; shows progress via stdout (TUI-ready)

Environment variables:
- POLL_INTERVAL   — seconds between polls (default 5)
- CMD_TIMEOUT     — max command execution seconds (default 60)
- SAFE_MODE       — if '1', only allowed commands are executed (default 1)
- ALLOWED_CMDS    — comma-separated list of allowed commands (default: echo,ls,pwd,cat,whoami,date,uname)
"""
import sys
import time
import os
import pwd
import subprocess
import requests
import shlex
from datetime import datetime, timezone

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8000'
PROV = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('PROVISION_TOKEN')

if not PROV:
    print('Provision token required')
    sys.exit(2)

POLL_INTERVAL = int(os.environ.get('POLL_INTERVAL', '5'))
CMD_TIMEOUT = int(os.environ.get('CMD_TIMEOUT', '60'))
SAFE_MODE = os.environ.get('SAFE_MODE', '1') == '1'
ALLOWED_CMDS = set(
    c.strip() for c in os.environ.get('ALLOWED_CMDS', 'echo,ls,pwd,cat,whoami,date,uname,df,free').split(',')
)

session = requests.Session()


def drop_privileges():
    """If running as root, switch to 'nobody' user."""
    if os.geteuid() == 0:
        nobody = pwd.getpwnam('nobody')
        os.setgid(nobody.pw_gid)
        os.setuid(nobody.pw_uid)
        print('Dropped privileges to nobody')


def send_log(agent_id, cmd_id, chunk, stream='stdout'):
    try:
        session.post(
            f'{BASE}/agent/{agent_id}/logs',
            json={'cmd_id': cmd_id, 'chunk': chunk, 'stream': stream},
            timeout=5,
        )
    except Exception as e:
        print(f'[WARN] Failed to send log: {e}')


def send_result(vcoo_id, cmd_id, summary):
    try:
        session.post(
            f'{BASE}/vcoo/{vcoo_id}/commands/{cmd_id}/result',
            json={'result': summary},
            timeout=5,
        )
    except Exception as e:
        print(f'[WARN] Failed to send result: {e}')


def is_allowed(command: str) -> bool:
    """Check if command is in the allowed whitelist (first word only)."""
    if not SAFE_MODE:
        return True
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if not tokens:
        return False
    base_cmd = os.path.basename(tokens[0])
    return base_cmd in ALLOWED_CMDS


def execute_command(command: str, agent_id: str, cmd_id: str) -> str:
    """Execute command with sandbox, streaming logs, return summary."""
    if not is_allowed(command):
        summary = f"BLOCKED by safe mode: '{command}' is not in allowed commands"
        print(summary)
        send_log(agent_id, cmd_id, summary + '\n', 'stderr')
        return summary

    print(f'Executing: {command}')
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid,  # create new session for clean kill
        )
        # Stream stdout line by line
        if proc.stdout:
            for line in proc.stdout:
                print(f'  {line.rstrip()}')
                send_log(agent_id, cmd_id, line, 'stdout')

        # Stream stderr
        if proc.stderr:
            for line in proc.stderr:
                print(f'  [stderr] {line.rstrip()}')
                send_log(agent_id, cmd_id, line, 'stderr')

        try:
            exit_code = proc.wait(timeout=CMD_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            summary = f"TIMEOUT after {CMD_TIMEOUT}s: '{command}'"
            send_log(agent_id, cmd_id, summary + '\n', 'stderr')
            return summary

        if exit_code == 0:
            summary = f"OK (exit 0): '{command}'"
        else:
            summary = f"FAILED (exit {exit_code}): '{command}'"
        return summary

    except Exception as e:
        summary = f"ERROR: {e}"
        send_log(agent_id, cmd_id, summary + '\n', 'stderr')
        return summary


def register():
    resp = session.post(
        f'{BASE}/register',
        json={'token': PROV, 'info': {'hostname': os.uname().nodename}},
        timeout=10,
    )
    if resp.status_code != 200:
        print('register failed', resp.status_code, resp.text)
        return None
    j = resp.json()
    print('Registered agent_id', j.get('agent_id'))
    return j


def poll_loop(agent_id, agent_token, vcoo_id):
    headers = {'Authorization': f'Bearer {agent_token}'}
    print(f'Poll loop started (interval={POLL_INTERVAL}s, safe_mode={SAFE_MODE})')
    try:
        while True:
            r = session.get(f'{BASE}/agent/{agent_id}/poll', headers=headers, timeout=10)
            if r.status_code == 200:
                j = r.json()
                cmds = j.get('commands', [])
                for c in cmds:
                    cmd_id = c.get('cmd_id')
                    command = c.get('command')
                    ts = datetime.now(timezone.utc).isoformat()
                    print(f'{ts} CMD {cmd_id}: {command}')
                    summary = execute_command(command, agent_id, cmd_id)
                    send_result(vcoo_id, cmd_id, summary)
                    print(f'{ts} DONE {cmd_id}: {summary}')
            elif r.status_code == 401:
                print('Auth expired, exiting')
                break
            else:
                print(f'poll returned {r.status_code}')
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print('Interrupted, exiting')


def main():
    drop_privileges()
    meta = register()
    if not meta:
        sys.exit(1)
    agent_id = meta.get('agent_id')
    agent_token = meta.get('agent_token')
    vcoo_id = meta.get('vcoo_id')
    poll_loop(agent_id, agent_token, vcoo_id)


if __name__ == '__main__':
    main()
