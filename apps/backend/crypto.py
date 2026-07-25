#!/usr/bin/env python3
"""crypto.py — Encrypt/decrypt API keys for remote agent configuration.

Flow:
  Backend: encrypt_api_key(api_key, seed_key, agent_id) → base64 token
  Agent:   _crypto_decrypt(token, encryption_key, agent_id) → plaintext

Both sides use PBKDF2-HMAC-SHA256 key derivation + XOR stream cipher
with SHA-256 keystream + HMAC-SHA256 integrity check.

This uses ONLY Python stdlib (hashlib, base64) so the agent needs
NO extra packages. The backend also uses stdlib (not cryptography).
"""

import base64
import hashlib
import os

_CRYPTO_ITERS = 100000

def _derive_key(seed_key: str, agent_id: str, salt: bytes) -> bytes:
    """Derive a 32-byte key from seed_key + agent_id + salt."""
    seed = (seed_key + ":" + agent_id).encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", seed, salt, _CRYPTO_ITERS, dklen=32)


def encrypt_api_key(api_key: str, seed_key: str, agent_id: str) -> str:
    """Encrypt an API key so only the target agent can decrypt it.

    Token format (urlsafe-base64, 16+16+N+32 bytes):
      salt(16) || iv(16) || ciphertext(N) || hmac(32)

    Returns a url-safe base64 string (no trailing = for compactness).
    """
    plaintext = api_key.encode("utf-8")
    salt = os.urandom(16)
    iv = os.urandom(16)

    key = _derive_key(seed_key, agent_id, salt)

    # Encrypt: XOR plaintext with keystream = SHA-256(key + iv + counter)
    ciphertext = bytearray()
    counter = 0
    for offset in range(0, len(plaintext), 32):
        keystream = hashlib.sha256(key + iv + bytes([counter])).digest()
        chunk = plaintext[offset:offset + 32]
        for i in range(len(chunk)):
            ciphertext.append(chunk[i] ^ keystream[i])
        counter += 1

    # HMAC for integrity
    hmac = hashlib.sha256(key + iv + bytes(ciphertext)).digest()

    token = salt + iv + bytes(ciphertext) + hmac
    return base64.urlsafe_b64encode(token).decode("utf-8").rstrip("=")


def decrypt_api_key(token_b64: str, encryption_key: str, agent_id: str) -> str:
    """Decrypt a token using the agent's encryption_key + agent_id.

    Compatible with agent_http's _crypto_decrypt.
    """
    # Add padding
    s = token_b64
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding

    raw = base64.urlsafe_b64decode(s)

    if len(raw) < 48:
        raise ValueError("token demasiado corto")

    salt = raw[:16]
    iv = raw[16:32]
    ciphertext = raw[32:-32]
    expected_hmac = raw[-32:]

    key = _derive_key(encryption_key, agent_id, salt)

    # Verify HMAC
    h = hashlib.sha256(key + iv + ciphertext).digest()
    if not _constant_time_compare(h, expected_hmac):
        raise ValueError("HMAC inválido")

    # Decrypt: XOR ciphertext with keystream
    plain = bytearray()
    counter = 0
    for offset in range(0, len(ciphertext), 32):
        keystream = hashlib.sha256(key + iv + bytes([counter])).digest()
        chunk = ciphertext[offset:offset + 32]
        for i in range(len(chunk)):
            plain.append(chunk[i] ^ keystream[i])
        counter += 1

    return bytes(plain).decode("utf-8")


def generate_encryption_key(master_key: str, agent_id: str) -> str:
    """Generate the encryption key that the agent stores locally.

    This is the raw PBKDF2-derived key using a fixed salt of agent_id.
    Note: the actual encryption uses a per-message random salt, so this
    generated key is the 'password' for PBKDF2, not the full key.
    """
    # Use a deterministic salt = agent_id bytes for key generation
    salt = agent_id.encode("utf-8")[:16].ljust(16, b"\x00")
    key = _derive_key(master_key, agent_id, salt)
    return base64.urlsafe_b64encode(key).decode("utf-8").rstrip("=")


def _constant_time_compare(a: bytes, b: bytes) -> bool:
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= x ^ y
    return result == 0
