import jwt
import os
import uuid
import logging
from datetime import datetime, timedelta
from fastapi import Header, HTTPException

logging.basicConfig(level=logging.DEBUG)

# MASTER_KEY read dynamically from environment

def _get_master_key():
    key = os.getenv('MASTER_KEY')
    if not key:
        raise RuntimeError('MASTER_KEY not set')
    return key

# Provision token (signed JWT)
def create_provision_token(vcoo_id: str, expires_minutes: int = 60):
    key = _get_master_key()
    jti = str(uuid.uuid4())
    payload = {
        'vcoo_id': vcoo_id,
        'jti': jti,
        'exp': datetime.utcnow() + timedelta(minutes=expires_minutes)
    }
    token = jwt.encode(payload, key, algorithm='HS256')
    return token

def decode_provision_token(token: str):
    key = os.getenv('MASTER_KEY')
    if not key:
        return None
    try:
        payload = jwt.decode(token, key, algorithms=['HS256'])
        return payload
    except Exception:
        return None

# Agent token
def create_agent_token(agent_id: str, expires_days: int = 30):
    key = _get_master_key()
    jti = str(uuid.uuid4())
    payload = {
        'agent_id': agent_id,
        'jti': jti,
        'exp': datetime.utcnow() + timedelta(days=expires_days)
    }
    token = jwt.encode(payload, key, algorithm='HS256')
    return token

def decode_agent_token(token: str):
    key = os.getenv('MASTER_KEY')
    if not key:
        return None
    try:
        payload = jwt.decode(token, key, algorithms=['HS256'])
        return payload
    except Exception:
        return None

# Dashboard password verification (dev: hardcoded 'versus')
_DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'versus')

def verify_dashboard_password(password: str) -> bool:
    """Simple password check for dashboard access. Dev default: 'versus'."""
    return password == _DASHBOARD_PASSWORD

# Minimal operator verification for WS UI
def verify_operator(authorization: str = Header(None)) -> str:
    """FastAPI dependency to verify an operator token in Authorization header.
    For POC we accept an OP_TOKEN from env or default 'op-test-token'.
    """
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail='operator auth missing')
    token = authorization.split(None, 1)[1]
    expected = os.getenv('OP_TOKEN', 'op-test-token')
    if token != expected:
        raise HTTPException(status_code=403, detail='invalid operator token')
    return token
