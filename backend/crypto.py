from cryptography.fernet import Fernet
import os

MASTER_KEY = os.getenv('MASTER_KEY')

def encrypt_secret(plaintext: str) -> str:
    if not MASTER_KEY:
        raise Exception('MASTER_KEY not set')
    f = Fernet(MASTER_KEY.encode())
    return f.encrypt(plaintext.encode()).decode()

def decrypt_secret(token: str) -> str:
    if not MASTER_KEY:
        raise Exception('MASTER_KEY not set')
    f = Fernet(MASTER_KEY.encode())
    return f.decrypt(token.encode()).decode()
