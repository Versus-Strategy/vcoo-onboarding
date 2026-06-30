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

# Operator login token
def create_operator_token(email: str, name: str, expires_hours: int = 24):
    """Create a JWT for operator dashboard login."""
    key = _get_master_key()
    payload = {
        'email': email,
        'role': 'operador',
        'name': name,
        'exp': datetime.utcnow() + timedelta(hours=expires_hours)
    }
    token = jwt.encode(payload, key, algorithm='HS256')
    return token

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


# ── Client auth ─────────────────────────────────────────────

import hashlib
import secrets

def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with a random salt."""
    salt = secrets.token_hex(16)
    hash_val = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hash_val}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    try:
        salt, hash_val = hashed.split(":", 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == hash_val
    except (ValueError, AttributeError):
        return False


def create_client_token(client_id: str, vcoo_id: str, email: str, expires_days: int = 30) -> str:
    """Create a JWT for an authenticated client."""
    key = _get_master_key()
    payload = {
        'client_id': client_id,
        'vcoo_id': vcoo_id,
        'email': email,
        'role': 'cliente',
        'exp': datetime.utcnow() + timedelta(days=expires_days),
    }
    token = jwt.encode(payload, key, algorithm='HS256')
    return token


def verify_client_token(token: str) -> dict | None:
    """Decode and verify a client JWT. Returns payload or None."""
    key = os.getenv('MASTER_KEY')
    if not key:
        return None
    try:
        payload = jwt.decode(token, key, algorithms=['HS256'])
        return payload
    except Exception:
        return None


def get_client_from_token(authorization: str = Header(None)) -> dict:
    """FastAPI dependency that extracts the client from the bearer token.
    Raises 401 if invalid or missing.
    """
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail='Token de cliente requerido')
    token = authorization.split(None, 1)[1]
    payload = verify_client_token(token)
    if not payload or payload.get('role') != 'cliente':
        raise HTTPException(status_code=401, detail='Token inválido o expirado')
    return payload
