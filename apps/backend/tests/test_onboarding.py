"""Tests del wizard de onboarding público (/setup/{identifier}).

Nota: /setup/{identifier} usa el UUID del VCOO como identificador (no el token).
Es read-only y sin auth devuelve requires_registration.
"""


class TestOnboarding:
    # ── /setup/{id} (read-only) ──

    def test_setup_no_auth_requires_registration(self, client, make_vcoo):
        vid = make_vcoo("Wizard")
        r = client.get(f"/setup/{vid}")
        assert r.status_code == 200
        d = r.json()
        assert d["requires_registration"] is True
        assert d["token_valid"] is True
        assert d["vcoo_name"] == "Wizard"

    def test_setup_invalid_identifier_400(self, client):
        r = client.get("/setup/not-a-real-vcoo")
        assert r.status_code == 400
        assert r.json()["detail"]["error"] == "token_invalid"

    def test_setup_operator_gets_full_state(self, client, operator_token, make_vcoo):
        vid = make_vcoo("WizardOp")
        r = client.get(
            f"/setup/{vid}",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["requires_registration"] is False
        assert d["vcoo_id"] == vid
        assert "install_command" in d
        assert "step" in d
        assert "progress" in d

    def test_setup_wrong_client_forbidden(self, client, make_vcoo, provision_token):
        """Un cliente autenticado que NO es dueño del VCOO recibe 403."""
        # VCOO A: registramos un cliente
        vid_a = make_vcoo("Owned")
        pt_a = provision_token(vid_a)
        reg = client.post("/auth/client/register", json={
            "name": "Owner", "email": "owner@t.com", "password": "p", "token": pt_a,
        })
        assert reg.status_code == 200
        client_token = reg.json()["token"]

        # VCOO B: distinto, el cliente A no debe poder verlo
        vid_b = make_vcoo("Other")
        r = client.get(
            f"/setup/{vid_b}",
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert r.status_code == 403

    # ── /setup/{id}/verify (modo demo, sin agente) ──

    def test_verify_auto_completes_in_demo_mode(self, client, make_vcoo):
        """Sin agente conectado, verify auto-avanza el paso (modo demo)."""
        vid = make_vcoo("VerifyDemo")
        r = client.post(f"/setup/{vid}/verify")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "auto_completed"
        assert "step" in d
        assert "next_step" in d

    def test_verify_invalid_identifier_400(self, client):
        r = client.post("/setup/nope/verify")
        assert r.status_code == 400
        assert r.json()["detail"]["error"] == "token_invalid"

    # ── /setup/{id}/auth-url ──

    def test_auth_url_unsupported_service_400(self, client, make_vcoo):
        vid = make_vcoo("AuthUrl")
        r = client.get(f"/setup/{vid}/auth-url", params={"service": "myspace"})
        assert r.status_code == 400

    def test_auth_url_github_returns_instructions(self, client, make_vcoo):
        vid = make_vcoo("AuthUrlGh")
        r = client.get(f"/setup/{vid}/auth-url", params={"service": "github"})
        assert r.status_code == 200
        d = r.json()
        assert d["service"] == "github"
        assert "instructions" in d

    def test_auth_url_invalid_identifier_400(self, client):
        r = client.get("/setup/nope/auth-url", params={"service": "github"})
        assert r.status_code == 400
