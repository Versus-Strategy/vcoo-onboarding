"""Tests del módulo de cifrado/descifrado de API keys."""
import pytest
from crypto import encrypt_api_key, decrypt_api_key


class TestCrypto:
    def test_encrypt_decrypt_roundtrip(self):
        """Cifrar y descifrar debe devolver el valor original."""
        plain = "sk-real-secret-key-12345"
        enc_key = "test-encryption-key-for-agent"
        agent_id = "test-agent-abc-123"
        encrypted = encrypt_api_key(plain, enc_key, agent_id)
        assert encrypted != plain
        assert len(encrypted) > 20
        decrypted = decrypt_api_key(encrypted, enc_key, agent_id)
        assert decrypted == plain

    def test_different_keys_produce_different_tokens(self):
        """Distintas encryption_key deben producir tokens distintos."""
        plain = "sk-test-key"
        t1 = encrypt_api_key(plain, "key-a", "agent-1")
        t2 = encrypt_api_key(plain, "key-b", "agent-1")
        assert t1 != t2

    def test_different_agents_produce_different_tokens(self):
        """Distintos agent_id deben producir tokens distintos."""
        plain = "sk-test-key"
        t1 = encrypt_api_key(plain, "same-key", "agent-1")
        t2 = encrypt_api_key(plain, "same-key", "agent-2")
        assert t1 != t2

    def test_decrypt_wrong_key_raises(self):
        """Descifrar con key incorrecta debe fallar."""
        plain = "sk-secret-123"
        enc_key = "correct-key"
        wrong_key = "wrong-key"
        agent_id = "agent-1"
        encrypted = encrypt_api_key(plain, enc_key, agent_id)
        with pytest.raises(ValueError, match="HMAC"):
            decrypt_api_key(encrypted, wrong_key, agent_id)

    def test_decrypt_wrong_agent_raises(self):
        """Descifrar con agent_id incorrecto debe fallar."""
        plain = "sk-secret-123"
        enc_key = "same-key"
        encrypted = encrypt_api_key(plain, enc_key, "agent-1")
        with pytest.raises(ValueError, match="HMAC"):
            decrypt_api_key(encrypted, enc_key, "agent-2")

    def test_decrypt_short_token_raises(self):
        """Token demasiado corto debe lanzar ValueError."""
        with pytest.raises(ValueError, match="corto"):
            decrypt_api_key("abc", "key", "agent")

    def test_decrypt_garbage_token_raises(self):
        """Token basura debe fallar."""
        with pytest.raises((ValueError, Exception)):
            decrypt_api_key("aW52YWxpZC10b2tlbi1mb3ItdGVzdGluZw==", "key", "agent")

    def test_empty_api_key_encrypts(self):
        """API key vacía debe poder cifrarse (aunque no tenga sentido práctico)."""
        encrypted = encrypt_api_key("", "key", "agent")
        decrypted = decrypt_api_key(encrypted, "key", "agent")
        assert decrypted == ""

    def test_long_api_key_roundtrip(self):
        """API key larga debe funcionar."""
        plain = "sk-" + "a" * 200
        enc_key = "test-key-long"
        encrypted = encrypt_api_key(plain, enc_key, "agent-long")
        decrypted = decrypt_api_key(encrypted, enc_key, "agent-long")
        assert decrypted == plain
