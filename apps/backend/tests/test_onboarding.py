"""Tests del wizard de onboarding público (/setup/{identifier}).

Nota: /setup/{identifier} usa el UUID del VCOO como identificador (no el token).
Es read-only y sin auth devuelve requires_registration.
"""

import json


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

    def test_verify_auto_completes_in_demo_mode(self, client, operator_token, make_vcoo):
        """Sin agente conectado, verify auto-avanza el paso (modo demo)."""
        vid = make_vcoo("VerifyDemo")
        r = client.post(
            f"/setup/{vid}/verify",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "auto_completed"
        assert "step" in d
        assert "next_step" in d

    def test_verify_no_auth_401(self, client):
        r = client.post("/setup/nope/verify")
        assert r.status_code == 401

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

    # ── /setup/{id}/advance ──

    def test_advance_requires_auth(self, client, make_vcoo):
        vid = make_vcoo("AdvNoAuth")
        r = client.post(f"/setup/{vid}/advance")
        assert r.status_code == 401

    def test_advance_from_bootstrap(self, client, operator_token, make_vcoo):
        """Avanzar desde bootstrap debe funcionar."""
        vid = make_vcoo("AdvBootstrap")
        r = client.post(f"/setup/{vid}/advance",
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.status_code == 200
        assert r.json()["status"] == "advanced"

    def test_advance_when_already_done(self, client, operator_token, make_vcoo):
        """Avanzar cuando ya está en finalize debe devolver already_done."""
        vid = make_vcoo("AdvDone")
        # Avanzar varias veces hasta llegar al final
        for _ in range(5):
            client.post(f"/setup/{vid}/advance",
                headers={"Authorization": f"Bearer {operator_token}"})
        r = client.post(f"/setup/{vid}/advance",
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.json()["status"] in ("already_done", "advanced")

    def test_advance_wrong_client_forbidden(self, client, make_vcoo, provision_token):
        """Cliente que no es dueño no puede avanzar."""
        vid_a = make_vcoo("AdvOwned")
        pt = provision_token(vid_a)
        reg = client.post("/auth/client/register", json={
            "name": "Owner", "email": "adv_owner@t.com", "password": "p", "token": pt,
        })
        ct = reg.json()["token"]
        vid_b = make_vcoo("AdvOther")
        r = client.post(f"/setup/{vid_b}/advance",
            headers={"Authorization": f"Bearer {ct}"})
        assert r.status_code == 403

    # ── Flujo completo: set-provider → capabilities → advance ──

    def test_full_provider_flow(self, client, make_vcoo, provision_token):
        """Flujo completo de configuración de proveedor vía wizard.

        Simula: crear VCOO → registrar agente → registrar cliente →
        bootstrap (verify + result) → set-provider (cifrado) →
        capabilities → advance → verificar estado final.
        """
        vid = make_vcoo("FullProv")
        pt = provision_token(vid)

        # 1. Registrar agente (obtener encryption_key)
        r = client.post("/register", json={"token": pt, "info": {}})
        assert r.status_code == 200
        reg = r.json()
        aid = reg["agent_id"]
        atk = reg["agent_token"]
        assert reg.get("encryption_key"), "encryption_key debe generarse"

        # 2. Registrar cliente (usando UUID como fallback)
        r = client.post("/auth/client/register", json={
            "name": "ProvClient", "email": "prov@t.com", "password": "p",
            "token": vid,  # UUID directo
        })
        assert r.status_code == 200
        ct = r.json()["token"]

        # 3. Verify bootstrap con token de operador (auto-avanza modo demo)
        r = client.post(f"/setup/{vid}/verify",
            headers={"Authorization": f"Bearer {ct}"})
        assert r.status_code == 200

        # 4. Simular que el agente procesa verify-bootstrap
        poll = client.get(f"/agent/{aid}/poll",
            headers={"Authorization": f"Bearer {atk}"}).json()
        vcmds = [c for c in poll.get("commands", []) if c["command"] == "verify-bootstrap"]
        if vcmds:
            cmd = vcmds[0]
            r = client.post(f"/agent/{aid}/result",
                json={"cmd_id": cmd["cmd_id"], "step": cmd["step"],
                      "status": "ok", "output": "bootstrap OK"},
                headers={"Authorization": f"Bearer {atk}"})
            assert r.status_code in (200, 201)

        # 5. Reportar capabilities (proveedores disponibles)
        caps_payload = {
            "providers": [{"id": "openai", "name": "OpenAI",
                          "auth": {"type": "api_key", "credential": "OPENAI_API_KEY"}}],
            "checks": {},
            "models": {},
        }
        r = client.post(f"/agent/{aid}/capabilities",
            json=caps_payload,
            headers={"Authorization": f"Bearer {atk}"})
        assert r.status_code == 200

        # 6. Obtener estado del onboarding (debe haber avanzado)
        r = client.get(f"/setup/{vid}",
            headers={"Authorization": f"Bearer {ct}"})
        assert r.status_code == 200
        state = r.json()
        assert "step" in state
        assert "wizard_step" in state

        # 7. Llamar a set-provider con API key (debe cifrarse si hay encryption_key)
        r = client.post(f"/setup/{vid}/set-provider",
            json={"provider": "openai", "api_key": "sk-test-secret-98765"},
            headers={"Authorization": f"Bearer {ct}"})
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "command_sent"
        assert d["cmd_id"]

        # 8. Verificar que el comando tiene el formato correcto (cifrado o plano)
        poll2 = client.get(f"/agent/{aid}/poll",
            headers={"Authorization": f"Bearer {atk}"}).json()
        sp_cmds = [c for c in poll2.get("commands", []) if c["command"] == "set-provider"]
        if sp_cmds:
            payload = sp_cmds[0].get("payload", {})
            # Si hay encryption_key, el payload debe tener 'encrypted' (string)
            # Si no, debe tener 'api_key' en texto plano
            if reg.get("encryption_key"):
                assert "encrypted" in payload, \
                    f"Con encryption_key el payload debe ir cifrado, got: {payload}"
                assert isinstance(payload["encrypted"], str), \
                    f"encrypted debe ser string base64, got: {type(payload['encrypted'])}"
                assert len(payload["encrypted"]) > 20
            else:
                assert payload.get("api_key") == "sk-test-secret-98765"

        # 9. Simular que el agente procesa set-provider y reporta checks
        if sp_cmds:
            cmd = sp_cmds[0]
            r = client.post(f"/agent/{aid}/result",
                json={"cmd_id": cmd["cmd_id"], "step": cmd.get("step", ""),
                      "status": "ok", "output": "provider configured"},
                headers={"Authorization": f"Bearer {atk}"})
            assert r.status_code in (200, 201)

        # 10. Reportar capabilities actualizadas (checks.provider = ok)
        caps_payload["checks"] = {"provider": "ok"}
        r = client.post(f"/agent/{aid}/capabilities",
            json=caps_payload,
            headers={"Authorization": f"Bearer {atk}"})
        assert r.status_code == 200

        # 11. Verificar que el estado refleja el provider OK
        r = client.get(f"/setup/{vid}",
            headers={"Authorization": f"Bearer {ct}"})
        state2 = r.json()
        checks = state2.get("checks", {})
        assert checks.get("provider") == "ok", \
            f"Provider check debe ser 'ok', got: {checks.get('provider')}"

        # 12. Avanzar paso vía advance (si ya está en finalize, skip)
        r = client.post(f"/setup/{vid}/advance",
            headers={"Authorization": f"Bearer {ct}"})
        assert r.status_code == 200
        adv_status = r.json().get("status", "")
        assert adv_status in ("advanced", "already_done"), \
            f"advance debe funcionar, got: {adv_status}"

        # 13. Verificar estado final — debe tener al menos bootstrap completado
        r = client.get(f"/setup/{vid}",
            headers={"Authorization": f"Bearer {ct}"})
        final = r.json()
        assert "bootstrap" in final.get("completed", []), \
            f"bootstrap debe estar completado, got: {final.get('completed')}"
