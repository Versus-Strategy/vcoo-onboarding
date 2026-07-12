import jwt
import os
import time
import uuid
import logging as _logging
from datetime import datetime, timedelta
from fastapi import Header, HTTPException
from db import SessionLocal

_logger = _logging.getLogger(__name__)
_logger.setLevel(_logging.DEBUG if os.getenv("VERCEL_ENV") is None else _logging.INFO)


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
        if _is_jti_revoked(payload.get('jti', '')):
            return None
        return payload
    except Exception:
        return None

# Dashboard password verification
_DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD')
if not _DASHBOARD_PASSWORD:
    if os.getenv('VERCEL_ENV'):
        raise RuntimeError("DASHBOARD_PASSWORD must be set in production")
    _DASHBOARD_PASSWORD = 'versus'  # dev default only

def verify_dashboard_password(password: str) -> bool:
    """Simple password check for dashboard access."""
    return password == _DASHBOARD_PASSWORD

# Operator login token
def create_operator_token(email: str, name: str, operator_id: str = '', expires_hours: int = 24):
    """Create a JWT for operator dashboard login."""
    key = _get_master_key()
    jti = str(uuid.uuid4())
    payload = {
        'email': email,
        'role': 'operador',
        'name': name,
        'operator_id': operator_id,
        'jti': jti,
        'exp': datetime.utcnow() + timedelta(hours=expires_hours)
    }
    token = jwt.encode(payload, key, algorithm='HS256')
    return token

# JWT-based operator verification (used by dashboard API calls)
def verify_operator_jwt(authorization: str = Header(None)) -> dict:
    """FastAPI dependency: verify operator JWT from Authorization header."""
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail='Autenticación requerida')
    token = authorization.split(None, 1)[1]
    key = os.getenv('MASTER_KEY')
    if not key:
        raise HTTPException(status_code=500, detail='MASTER_KEY no configurada')
    try:
        payload = jwt.decode(token, key, algorithms=['HS256'])
        if payload.get('role') != 'operador':
            raise HTTPException(status_code=403, detail='Se requiere rol de operador')
        if _is_jti_revoked(payload.get('jti', '')):
            raise HTTPException(status_code=401, detail='Token revocado')
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail='Token expirado')
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail='Token inválido')

# Operator JWT verification for WebSocket UI
def verify_operator(authorization: str = Header(None)) -> str:
    """FastAPI dependency: verify operator JWT for WebSocket connections.
    Accepts the same operator bearer token as verify_operator_jwt."""
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail='operator auth missing')
    token = authorization.split(None, 1)[1]
    key = os.getenv('MASTER_KEY')
    if not key:
        raise HTTPException(status_code=500, detail='MASTER_KEY no configurada')
    try:
        payload = jwt.decode(token, key, algorithms=['HS256'])
        if payload.get('role') != 'operador':
            raise HTTPException(status_code=403, detail='invalid operator token')
        if _is_jti_revoked(payload.get('jti', '')):
            raise HTTPException(status_code=401, detail='Token revocado')
        return token
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail='Token expirado')
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail='invalid operator token')


# ── Client auth ─────────────────────────────────────────────

import bcrypt

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


_jti_cache: dict[str, tuple[bool, float]] = {}
_JTI_CACHE_TTL = 30  # segundos


def _reset_jti_cache():
    """Clear the JTI revocation cache (used by test teardown)."""
    _jti_cache.clear()


def _invalidate_jti(jti: str):
    """Remove a specific JTI from the cache (called when token is revoked)."""
    _jti_cache.pop(jti, None)


def _is_jti_revoked(jti: str) -> bool:
    """Check if a JWT ID has been revoked. Uses a short-lived in-memory cache."""
    if not jti:
        return False
    now = time.time()
    if jti in _jti_cache:
        result, ts = _jti_cache[jti]
        if now - ts < _JTI_CACHE_TTL:
            return result
        del _jti_cache[jti]
    if len(_jti_cache) > 500:
        _jti_cache.clear()
    try:
        db = SessionLocal()
        from crud import is_token_revoked as _check
        result = _check(db, jti)
        db.close()
        _jti_cache[jti] = (result, now)
        return result
    except Exception:
        return False


def decode_token_ignore_expiry(token: str) -> dict | None:
    """Decode a JWT without checking expiration (for refresh). Validates signature only."""
    key = os.getenv('MASTER_KEY')
    if not key:
        return None
    try:
        payload = jwt.decode(token, key, algorithms=['HS256'], options={"verify_exp": False})
        if _is_jti_revoked(payload.get('jti', '')):
            return None
        return payload
    except Exception:
        return None


def create_client_token(client_id: str, vcoo_id: str, email: str, expires_days: int = 30) -> str:
    """Create a JWT for an authenticated client."""
    key = _get_master_key()
    jti = str(uuid.uuid4())
    payload = {
        'client_id': client_id,
        'vcoo_id': vcoo_id,
        'email': email,
        'role': 'cliente',
        'jti': jti,
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
        if _is_jti_revoked(payload.get('jti', '')):
            return None
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
