import jwt
import os
import uuid
from datetime import datetime, timedelta

MASTER_KEY = os.getenv('MASTER_KEY', 'REPLACE_ME')

# Provision token: short lived
def create_provision_token(vcoo_id: str, expires_minutes=60):
    exp = datetime.utcnow() + timedelta(minutes=expires_minutes)
    payload = {"vcoo_id": vcoo_id, "exp": exp.timestamp(), "jti": str(uuid.uuid4())}
    return jwt.encode(payload, MASTER_KEY, algorithm="HS256")

def decode_provision_token(token: str):
    try:
        payload = jwt.decode(token, MASTER_KEY, algorithms=["HS256"])
        return payload
    except Exception:
        return None

# Agent token: longer lived, contains agent_id and jti for revocation
def create_agent_token(agent_id: str, expires_days=30):
    exp = datetime.utcnow() + timedelta(days=expires_days)
    payload = {"agent_id": agent_id, "exp": exp.timestamp(), "jti": str(uuid.uuid4())}
    return jwt.encode(payload, MASTER_KEY, algorithm="HS256")

def decode_agent_token(token: str):
    try:
        payload = jwt.decode(token, MASTER_KEY, algorithms=["HS256"])
        return payload
    except Exception:
        return None
