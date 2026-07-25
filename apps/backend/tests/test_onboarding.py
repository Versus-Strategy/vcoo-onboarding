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
        vid_a = make_vcoo("Owned")
        pt_a = provision_token(vid_a)
        reg = client.post("/auth/client/register", json={
            "name": "Owner", "email": "owner@t.com", "password": "p", "token": pt_a,
        })
        assert reg.status_code == 200
        client_token = reg.json()["token"]
        vid_b = make_vcoo("Other")
        r = client.get(
            f"/setup/{vid_b}",
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert r.status_code == 403

    # ── /setup/{id}/verify (modo demo, sin agente) ──

    def test_verify_auto_completes_in_demo_mode(self, client, operator_token, make_vcoo):
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
        vid = make_vcoo("AdvBootstrap")
        r = client.post(f"/setup/{vid}/advance",
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.status_code == 200
        assert r.json()["status"] == "advanced"

    def test_advance_when_already_done(self, client, operator_token, make_vcoo):
        vid = make_vcoo("AdvDone")
        for _ in range(5):
            client.post(f"/setup/{vid}/advance",
                headers={"Authorization": f"Bearer {operator_token}"})
        r = client.post(f"/setup/{vid}/advance",
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.json()["status"] in ("already_done", "advanced")

    def test_advance_wrong_client_forbidden(self, client, make_vcoo, provision_token):
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
        vid = make_vcoo("FullProv")
        pt = provision_token(vid)

        r = client.post("/register", json={"token": pt, "info": {}})
        assert r.status_code == 200
        reg = r.json()
        aid = reg["agent_id"]
        atk = reg["agent_token"]
        assert reg.get("encryption_key"), "encryption_key debe generarse"

        r = client.post("/auth/client/register", json={
            "name": "ProvClient", "email": "prov@t.com", "password": "p",
            "token": vid,
        })
        assert r.status_code == 200
        ct = r.json()["token"]

        r = client.post(f"/setup/{vid}/verify",
            headers={"Authorization": f"Bearer {ct}"})
        assert r.status_code == 200

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

        r = client.get(f"/setup/{vid}",
            headers={"Authorization": f"Bearer {ct}"})
        assert r.status_code == 200
        state = r.json()
        assert "step" in state
        assert "wizard_step" in state

        r = client.post(f"/setup/{vid}/set-provider",
            json={"provider": "openai", "api_key": "sk-test-secret-98765"},
            headers={"Authorization": f"Bearer {ct}"})
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "command_sent"
        assert d["cmd_id"]

        poll2 = client.get(f"/agent/{aid}/poll",
            headers={"Authorization": f"Bearer {atk}"}).json()
        sp_cmds = [c for c in poll2.get("commands", []) if c["command"] == "set-provider"]
        if sp_cmds:
            payload = sp_cmds[0].get("payload", {})
            if reg.get("encryption_key"):
                assert "encrypted" in payload,                     f"Con encryption_key el payload debe ir cifrado, got: {payload}"
                assert isinstance(payload["encrypted"], str),                     f"encrypted debe ser string base64, got: {type(payload['encrypted'])}"
                assert len(payload["encrypted"]) > 20
            else:
                assert payload.get("api_key") == "sk-test-secret-98765"

        if sp_cmds:
            cmd = sp_cmds[0]
            r = client.post(f"/agent/{aid}/result",
                json={"cmd_id": cmd["cmd_id"], "step": cmd.get("step", ""),
                      "status": "ok", "output": "provider configured"},
                headers={"Authorization": f"Bearer {atk}"})
            assert r.status_code in (200, 201)

        caps_payload["checks"] = {"provider": "ok"}
        r = client.post(f"/agent/{aid}/capabilities",
            json=caps_payload,
            headers={"Authorization": f"Bearer {atk}"})
        assert r.status_code == 200

        r = client.get(f"/setup/{vid}",
            headers={"Authorization": f"Bearer {ct}"})
        state2 = r.json()
        checks = state2.get("checks", {})
        assert checks.get("provider") == "ok",             f"Provider check debe ser 'ok', got: {checks.get('provider')}"

        r = client.post(f"/setup/{vid}/advance",
            headers={"Authorization": f"Bearer {ct}"})
        assert r.status_code == 200
        adv_status = r.json().get("status", "")
        assert adv_status in ("advanced", "already_done"),             f"advance debe funcionar, got: {adv_status}"

        r = client.get(f"/setup/{vid}",
            headers={"Authorization": f"Bearer {ct}"})
        final = r.json()
        assert "bootstrap" in final.get("completed", []),             f"bootstrap debe estar completado, got: {final.get('completed')}"

    # ── /setup/{id}/set-provider (client endpoint) ──

    def test_set_provider_requires_auth(self, client, make_vcoo):
        vid = make_vcoo("ProvAuth")
        r = client.post(f"/setup/{vid}/set-provider", json={"provider": "openai", "api_key": "sk-foo"})
        assert r.status_code == 401

    def test_set_provider_invalid_identifier(self, client, operator_token):
        r = client.post("/setup/nope/set-provider",
            json={"provider": "openai", "api_key": "sk-foo"},
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.status_code == 400

    def test_set_provider_without_agent(self, client, make_vcoo, provision_token):
        vid = make_vcoo("NoAgentProv")
        pt = provision_token(vid)
        reg = client.post("/auth/client/register", json={
            "name": "NoAgent", "email": "noagent@t.com", "password": "p", "token": pt,
        })
        ct = reg.json()["token"]
        r = client.post(f"/setup/{vid}/set-provider",
            json={"provider": "openai", "api_key": "sk-foo"},
            headers={"Authorization": f"Bearer {ct}"})
        assert r.status_code == 400
        assert "agent not installed" in r.json()["detail"]

    def test_set_provider_success(self, client, make_vcoo, provision_token):
        vid = make_vcoo("ProvSuccess")
        pt = provision_token(vid)
        r = client.post("/register", json={"token": pt, "info": {}})
        assert r.status_code == 200
        reg = r.json()
        r = client.post("/auth/client/register", json={
            "name": "ProvOk", "email": "provok@t.com", "password": "p", "token": vid,
        })
        ct = r.json()["token"]
        r = client.post(f"/setup/{vid}/set-provider",
            json={"provider": "openai", "api_key": "sk-test-secret-98765"},
            headers={"Authorization": f"Bearer {ct}"})
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "command_sent"
        assert d["cmd_id"]

        from db import SessionLocal
        from models import Command
        db = SessionLocal()
        cmd = db.query(Command).filter(Command.id == d["cmd_id"]).first()
        assert cmd is not None
        assert cmd.command == "set-provider"
        db.close()

    # ── /vcoo/{id}/set-provider (operator endpoint) ──

    def test_set_provider_operator(self, client, operator_token, make_vcoo):
        vid = make_vcoo("OpProv")
        pt = client.get(f"/vcoo/{vid}/provision-token",
            headers={"Authorization": f"Bearer {operator_token}"}).json()["token"]
        r = client.post("/register", json={"token": pt, "info": {}})
        assert r.status_code == 200
        r = client.post(f"/vcoo/{vid}/set-provider",
            json={"provider": "anthropic", "api_key": "sk-ant-test"},
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "command_sent"
        assert d["cmd_id"]

    # ── OAuth callback ──

    def test_oauth_callback_error(self, client):
        r = client.get("/auth/callback", params={"error": "access_denied"})
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_oauth_callback_missing_code(self, client):
        r = client.get("/auth/callback")
        assert r.status_code == 400
        assert "text/html" in r.headers.get("content-type", "")

    def test_oauth_callback_with_state(self, client, make_vcoo):
        vid = make_vcoo("OAuthState")
        r = client.get("/auth/callback", params={"code": "fake-code", "state": f"{vid}:google"})
        assert "text/html" in r.headers.get("content-type", "")

    # ── Onboarding retry / skip ──

    def test_retry_step(self, client, operator_token, make_vcoo):
        vid = make_vcoo("RetryStep")
        from db import SessionLocal
        import crud as _crud
        db = SessionLocal()
        _crud.add_onboarding_error(db, vid, "bootstrap", "test error")
        db.close()
        r = client.post(f"/vcoo/{vid}/onboarding/retry",
            json={"step": "bootstrap"},
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.status_code == 200
        d = r.json()
        assert d["step"] == "bootstrap"
        assert d["onboarding_status"] == "in_progress"

    def test_skip_step(self, client, operator_token, make_vcoo):
        vid = make_vcoo("SkipStep")
        r = client.post(f"/vcoo/{vid}/onboarding/skip",
            json={"step": "bootstrap"},
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.status_code == 200
        d = r.json()
        assert d["step"] == "bootstrap"
        assert d["next_step"] == "whatsapp-setup"

    # ── Agent registration & security ──

    def test_valid_agent_commands_contains_all(self):
        """Verify all known steps have corresponding agent commands."""
        from onboarding import has_agent_command
        for step in ["bootstrap", "google-oauth", "gmail-setup", "trello-setup",
                     "github-setup", "vercel-setup", "supabase-setup", "whatsapp-setup", "finalize"]:
            assert has_agent_command(step), f"{step} missing from agent commands"

    def test_install_command_has_no_token_in_url(self, client, operator_token, make_vcoo):
        vid = make_vcoo("InstallNoLeak")
        r = client.get(f"/setup/{vid}",
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.status_code == 200
        cmd = r.json().get("install_command", "")
        assert "PROVISION_TOKEN=" in cmd
        assert "|" in cmd

    def test_register_invalid_token(self, client):
        r = client.post("/register", json={"token": "fake-token", "info": {}})
        assert r.status_code == 401

    def test_register_rate_limited(self, client, make_vcoo, provision_token):
        from ratelimit import _register_limiter
        _register_limiter._attempts.clear()
        for i in range(5):
            r = client.post("/register", json={"token": "bad-token", "info": {}})
            if r.status_code == 429:
                return
        assert r.status_code == 401

    def test_register_creates_agent(self, client, make_vcoo, provision_token):
        vid = make_vcoo("RegAgent")
        pt = provision_token(vid)
        r = client.post("/register", json={"token": pt, "info": {}})
        assert r.status_code == 200
        d = r.json()
        assert d["vcoo_id"] == vid
        assert d["agent_id"]
        assert d["agent_token"]
        assert d.get("encryption_key")

        from db import SessionLocal
        from models import Agent
        db = SessionLocal()
        agent = db.query(Agent).filter(Agent.id == d["agent_id"]).first()
        assert agent is not None
        assert str(agent.vcoo_id) == vid
        assert agent.encryption_key is not None
        db.close()

    # ── Advance flow ──

    def test_advance_through_all_steps(self, client, operator_token, make_vcoo):
        vid = make_vcoo("AdvAllSteps")
        r = client.post(f"/setup/{vid}/advance",
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.status_code == 200
        assert r.json()["status"] == "advanced"
        r = client.post(f"/setup/{vid}/advance",
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.status_code == 200
        assert r.json()["status"] == "advanced"
        r = client.post(f"/setup/{vid}/advance",
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.status_code == 200
        assert r.json()["status"] == "already_done"

    def test_advance_without_completing_previous(self, client, operator_token, make_vcoo):
        vid = make_vcoo("AdvSeq")
        r = client.post(f"/setup/{vid}/advance",
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.json()["status"] == "advanced"
        r = client.get(f"/setup/{vid}",
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.json()["step"] == "whatsapp-setup"
        r = client.post(f"/setup/{vid}/advance",
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.json()["status"] == "advanced"
        r = client.get(f"/setup/{vid}",
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.json()["step"] == "finalize"

    # ── Tick endpoint ──

    def test_tick_requires_auth(self, client, make_vcoo, provision_token):
        vid = make_vcoo("TickAuth")
        pt = provision_token(vid)
        r = client.post("/register", json={"token": pt, "info": {}})
        aid = r.json()["agent_id"]
        r = client.post(f"/agent/{aid}/tick", json={})
        assert r.status_code == 401

    def test_tick_health_update(self, client, make_vcoo, provision_token):
        vid = make_vcoo("TickHealth")
        pt = provision_token(vid)
        r = client.post("/register", json={"token": pt, "info": {}})
        aid = r.json()["agent_id"]
        atk = r.json()["agent_token"]
        r = client.post(f"/agent/{aid}/tick",
            json={"health": {"hostname": "test-box", "cpu_pct": 42.5}},
            headers={"Authorization": f"Bearer {atk}"})
        assert r.status_code == 200

        from db import SessionLocal
        from models import Agent
        import json
        db = SessionLocal()
        agent = db.query(Agent).filter(Agent.id == aid).first()
        assert agent is not None
        hp = json.loads(agent.health_payload) if agent.health_payload else {}
        assert hp.get("hostname") == "test-box"
        assert hp.get("cpu_pct") == 42.5
        db.close()

    def test_tick_returns_commands(self, client, make_vcoo, provision_token):
        vid = make_vcoo("TickCmds")
        pt = provision_token(vid)
        r = client.post("/register", json={"token": pt, "info": {}})
        aid = r.json()["agent_id"]
        atk = r.json()["agent_token"]
        r = client.post(f"/agent/{aid}/tick", json={},
            headers={"Authorization": f"Bearer {atk}"})
        assert r.status_code == 200
        d = r.json()
        assert "commands" in d
        assert "tick_interval" in d

    # ── Agent result edge cases ──

    def test_agent_result_missing_cmd_404(self, client, make_vcoo, provision_token):
        vid = make_vcoo("Result404")
        pt = provision_token(vid)
        r = client.post("/register", json={"token": pt, "info": {}})
        aid = r.json()["agent_id"]
        atk = r.json()["agent_token"]
        r = client.post(f"/agent/{aid}/result",
            json={"cmd_id": "00000000-0000-0000-0000-000000000000", "step": "bootstrap",
                  "status": "ok", "output": ""},
            headers={"Authorization": f"Bearer {atk}"})
        assert r.status_code == 404

    def test_agent_result_requires_auth(self, client, make_vcoo, provision_token):
        vid = make_vcoo("ResultAuth")
        pt = provision_token(vid)
        r = client.post("/register", json={"token": pt, "info": {}})
        aid = r.json()["agent_id"]
        r = client.post(f"/agent/{aid}/result",
            json={"cmd_id": "00000000-0000-0000-0000-000000000000", "step": "bootstrap",
                  "status": "ok", "output": ""})
        assert r.status_code == 401

    # ── Onboarding management edge cases ──

    def test_retry_nonexistent_vcoo(self, client, operator_token):
        r = client.post("/vcoo/nonexistent/onboarding/retry",
            json={"step": "bootstrap"},
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.status_code == 404

    def test_skip_nonexistent_vcoo(self, client, operator_token):
        r = client.post("/vcoo/nonexistent/onboarding/skip",
            json={"step": "bootstrap"},
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.status_code == 404

    # ── Token regeneration ──

    def test_regenerate_token_changes_value(self, client, operator_token, make_vcoo):
        vid = make_vcoo("RegenToken")
        r = client.get(f"/vcoo/{vid}/provision-token",
            headers={"Authorization": f"Bearer {operator_token}"})
        old_token = r.json()["token"]
        r = client.post(f"/vcoo/{vid}/regenerate-token",
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.status_code == 200
        new_token = r.json()["token"]
        assert new_token != old_token

    # ── Register with info ──

    def test_register_with_info(self, client, make_vcoo, provision_token):
        vid = make_vcoo("RegInfo")
        pt = provision_token(vid)
        r = client.post("/register", json={"token": pt, "info": {"hostname": "test-vps"}})
        assert r.status_code == 200
        assert r.json()["agent_id"]

    # ── /setup/{id}/start-pair-whatsapp ──

    def test_start_pair_whatsapp_requires_auth(self, client, make_vcoo):
        vid = make_vcoo("WspAuth")
        r = client.post(f"/setup/{vid}/start-pair-whatsapp", json={})
        assert r.status_code == 401

    def test_start_pair_whatsapp_no_agent(self, client, make_vcoo, provision_token):
        vid = make_vcoo("WspNoAgent")
        pt = provision_token(vid)
        reg = client.post("/auth/client/register", json={
            "name": "Wsp", "email": "wsp@t.com", "password": "p", "token": pt,
        })
        ct = reg.json()["token"]
        r = client.post(f"/setup/{vid}/start-pair-whatsapp", json={},
            headers={"Authorization": f"Bearer {ct}"})
        assert r.status_code == 400

    def test_start_pair_whatsapp_success(self, client, make_vcoo, provision_token):
        vid = make_vcoo("WspOk")
        pt = provision_token(vid)
        r = client.post("/register", json={"token": pt, "info": {}})
        atk = r.json()["agent_token"]
        reg = client.post("/auth/client/register", json={
            "name": "WspOk", "email": "wspok@t.com", "password": "p", "token": vid,
        })
        ct = reg.json()["token"]
        r = client.post(f"/setup/{vid}/start-pair-whatsapp", json={"phone": "+1234567890"},
            headers={"Authorization": f"Bearer {ct}"})
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "command_sent"
        assert d["cmd_id"]

    # ── /setup/{id}/whatsapp-qr ──

    def test_whatsapp_qr_requires_auth(self, client, make_vcoo):
        vid = make_vcoo("WspQrAuth")
        r = client.get(f"/setup/{vid}/whatsapp-qr")
        assert r.status_code == 401

    # ── /setup/{id}/hermes-commands ──

    def test_hermes_commands(self, client, make_vcoo):
        vid = make_vcoo("HermesCmd")
        r = client.get(f"/setup/{vid}/hermes-commands", params={"service": "google"})
        assert r.status_code == 200
        d = r.json()
        assert d["service"] == "google"
        assert len(d["commands"]) > 0

    def test_hermes_commands_invalid_vcoo(self, client):
        r = client.get("/setup/nope/hermes-commands", params={"service": "google"})
        assert r.status_code == 400

    # ── /vcoo/{id}/complete + /vcoo/{id}/reactivate ──

    def test_complete_vcoo_requires_auth(self, client, make_vcoo):
        vid = make_vcoo("CompVcoo")
        r = client.post(f"/vcoo/{vid}/complete")
        assert r.status_code == 401

    def test_complete_vcoo(self, client, operator_token, make_vcoo):
        vid = make_vcoo("CompOk")
        r = client.post(f"/vcoo/{vid}/complete",
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    def test_reactivate_vcoo(self, client, operator_token, make_vcoo):
        vid = make_vcoo("Reactivate")
        client.post(f"/vcoo/{vid}/complete",
            headers={"Authorization": f"Bearer {operator_token}"})
        r = client.post(f"/vcoo/{vid}/reactivate",
            headers={"Authorization": f"Bearer {operator_token}"})
        assert r.status_code == 200

    # ── /setup/{id}/encrypt-creds ──

    def test_encrypt_creds_requires_auth(self, client, make_vcoo):
        vid = make_vcoo("EncAuth")
        r = client.post(f"/setup/{vid}/encrypt-creds", json={"service": "gmail", "credentials": {"token": "abc"}})
        assert r.status_code == 401

    def test_encrypt_creds_no_agent(self, client, make_vcoo, provision_token):
        vid = make_vcoo("EncNoAgent")
        pt = provision_token(vid)
        reg = client.post("/auth/client/register", json={
            "name": "Enc", "email": "enc@t.com", "password": "p", "token": pt,
        })
        ct = reg.json()["token"]
        r = client.post(f"/setup/{vid}/encrypt-creds",
            json={"service": "gmail", "credentials": {"token": "abc"}},
            headers={"Authorization": f"Bearer {ct}"})
        assert r.status_code == 400

    # ── /agent/heartbeat + /agent/{id}/health ──

    def test_heartbeat_ack(self, client, make_vcoo, provision_token):
        vid = make_vcoo("HbVcoo")
        pt = provision_token(vid)
        r = client.post("/register", json={"token": pt, "info": {}})
        aid = r.json()["agent_id"]
        r = client.post("/agent/heartbeat", json={"agent_id": aid, "vcoo_id": vid})
        assert r.status_code == 200
        assert r.json()["ack"] is True

    def test_health_report(self, client, make_vcoo, provision_token):
        vid = make_vcoo("HealthVcoo")
        pt = provision_token(vid)
        r = client.post("/register", json={"token": pt, "info": {}})
        aid = r.json()["agent_id"]
        atk = r.json()["agent_token"]
        r = client.post(f"/agent/{aid}/health",
            json={"cpu_pct": 23.5, "memory_pct": 45.0},
            headers={"Authorization": f"Bearer {atk}"})
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
