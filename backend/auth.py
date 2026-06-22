import jwt
import os
from datetime import datetime, timedelta

MASTER_KEY = os.getenv('MASTER_KEY', 'REPLACE_ME')

def create_config_token(vcoo_id: str, expires_hours=1):
    exp = datetime.utcnow() + timedelta(hours=expires_hours)
    payload = {"vcoo_id": vcoo_id, "exp": exp.timestamp()}
    return jwt.encode(payload, MASTER_KEY, algorithm="HS256")

def decode_config_token(token: str):
    try:
        payload = jwt.decode(token, MASTER_KEY, algorithms=["HS256"])
        return payload
    except Exception:
        return None
