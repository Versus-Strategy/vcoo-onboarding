"""Tests de endpoints de utilidad: /healthz, /playbooks, /install.sh."""

from main import _install_command, _check_client_owns_vcoo, _safe_read_file, _TOKEN_INVALID_ERROR, _VALID_AGENT_COMMANDS
from db import SessionLocal
import crud


class TestUtils:
    def test_healthz(self, client):
        r = client.get("/healthz")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "ok"
        assert d["version"] == "v2"
        assert d["python"]

    def test_playbooks_list(self, client):
        r = client.get("/playbooks")
        assert r.status_code == 200
        assert "playbooks" in r.json()
        assert isinstance(r.json()["playbooks"], list)

    def test_playbook_unknown_404(self, client):
        r = client.get("/playbooks/does-not-exist.sh")
        assert r.status_code == 404

    def test_playbook_path_traversal_blocked(self, client):
        """Path traversal debe fallar (404 porque basename limpia el path)."""
        r = client.get("/playbooks/../../etc/passwd")
        assert r.status_code == 404

    def test_install_sh_served(self, client):
        r = client.get("/install.sh")
        assert r.status_code == 200
        assert len(r.text) > 0

    def test_install_command_format(self):
        cmd = _install_command("https://control.example.com", "test-token-123")
        assert "curl" in cmd
        assert "https://control.example.com" in cmd
        assert "test-token-123" in cmd
        assert cmd.startswith("curl -sSL")

    def test_valid_agent_commands_defined(self):
        assert "verify-bootstrap" in _VALID_AGENT_COMMANDS
        assert "verify-google" in _VALID_AGENT_COMMANDS
        assert "set-provider" in _VALID_AGENT_COMMANDS
        assert "save-creds" in _VALID_AGENT_COMMANDS
        assert "finalize" in _VALID_AGENT_COMMANDS
        assert len(_VALID_AGENT_COMMANDS) >= 10

    def test_token_invalid_error_has_required_keys(self):
        assert "error" in _TOKEN_INVALID_ERROR
        assert "message" in _TOKEN_INVALID_ERROR
        assert "action" in _TOKEN_INVALID_ERROR
        assert _TOKEN_INVALID_ERROR["error"] == "token_invalid"

    def test_check_client_owns_vcoo_no_client(self):
        """Cliente inexistente no es dueño de nada."""
        db = SessionLocal()
        try:
            assert not _check_client_owns_vcoo(db, "noone@t.com", "fake-id")
        finally:
            db.close()

    def test_security_headers_present(self, client):
        r = client.get("/healthz")
        assert r.headers.get("x-content-type-options") == "nosniff"
        assert r.headers.get("x-frame-options") == "DENY"
        assert r.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
