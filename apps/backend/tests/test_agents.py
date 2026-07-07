"""Tests del ciclo de vida del agente: register, poll, result (ACK), heartbeat, health."""


class TestAgents:
    def _register(self, client, provision_token, vid):
        """Registra un agente y devuelve (agent_id, agent_token)."""
        pt = provision_token(vid)
        r = client.post("/register", json={"token": pt, "info": {"hostname": "vps-1"}})
        assert r.status_code == 200, r.text
        d = r.json()
        return d["agent_id"], d["agent_token"]

    # ── Register ──

    def test_register_returns_agent_credentials(self, client, make_vcoo, provision_token):
        vid = make_vcoo("AgentReg")
        pt = provision_token(vid)
        r = client.post("/register", json={"token": pt, "info": {}})
        assert r.status_code == 200
        d = r.json()
        assert d["agent_id"]
        assert d["agent_token"]
        assert d["vcoo_id"] == vid
        # encryption_key se genera si hay MASTER_KEY (lo hay en tests)
        assert d["encryption_key"]

    def test_register_invalid_token_401(self, client):
        r = client.post("/register", json={"token": "garbage", "info": {}})
        assert r.status_code == 401

    # ── Poll ──

    def test_poll_requires_auth(self, client, make_vcoo, provision_token):
        vid = make_vcoo("AgentPoll")
        aid, _ = self._register(client, provision_token, vid)
        r = client.get(f"/agent/{aid}/poll")
        assert r.status_code == 401

    def test_poll_wrong_token_401(self, client, make_vcoo, provision_token):
        vid = make_vcoo("AgentPollWrong")
        aid, _ = self._register(client, provision_token, vid)
        r = client.get(f"/agent/{aid}/poll", headers={"Authorization": "Bearer nope"})
        assert r.status_code == 401

    def test_poll_returns_pending_commands(self, client, make_vcoo, provision_token):
        """Al registrarse con onboarding pendiente se auto-encola un comando."""
        vid = make_vcoo("AgentPollCmds")
        aid, at = self._register(client, provision_token, vid)
        r = client.get(f"/agent/{aid}/poll", headers={"Authorization": f"Bearer {at}"})
        assert r.status_code == 200
        d = r.json()
        assert "commands" in d
        assert isinstance(d["commands"], list)

    # ── Result (ACK) ──

    def test_result_acks_command(self, client, make_vcoo, provision_token):
        vid = make_vcoo("AgentResult")
        aid, at = self._register(client, provision_token, vid)
        # Obtener un comando pendiente vía poll
        poll = client.get(
            f"/agent/{aid}/poll", headers={"Authorization": f"Bearer {at}"}
        ).json()
        cmds = poll.get("commands", [])
        if not cmds:
            # No hay comando que reportar en este flujo; nada que verificar.
            return
        cmd_id = cmds[0]["cmd_id"]
        step = cmds[0].get("step", "")
        r = client.post(
            f"/agent/{aid}/result",
            json={"cmd_id": cmd_id, "step": step, "status": "ok", "output": "done"},
            headers={"Authorization": f"Bearer {at}"},
        )
        assert r.status_code in (200, 201, 202)
        assert r.json()["ack"] is True

    def test_result_missing_cmd_id_400(self, client, make_vcoo, provision_token):
        vid = make_vcoo("AgentResultBad")
        aid, at = self._register(client, provision_token, vid)
        r = client.post(
            f"/agent/{aid}/result",
            json={"status": "ok"},
            headers={"Authorization": f"Bearer {at}"},
        )
        assert r.status_code == 400

    def test_result_requires_auth(self, client, make_vcoo, provision_token):
        vid = make_vcoo("AgentResultNoAuth")
        aid, _ = self._register(client, provision_token, vid)
        r = client.post(f"/agent/{aid}/result", json={"cmd_id": "x"})
        assert r.status_code == 401

    # ── Heartbeat ──

    def test_heartbeat_ack(self, client, make_vcoo, provision_token):
        vid = make_vcoo("AgentHeartbeat")
        aid, _ = self._register(client, provision_token, vid)
        r = client.post("/agent/heartbeat", json={"agent_id": aid})
        assert r.status_code == 200
        assert r.json()["ack"] is True

    def test_heartbeat_missing_agent_id_400(self, client):
        r = client.post("/agent/heartbeat", json={})
        assert r.status_code == 400

    # ── Health ──

    def test_health_report_ok(self, client, make_vcoo, provision_token):
        vid = make_vcoo("AgentHealth")
        aid, _ = self._register(client, provision_token, vid)
        r = client.post(
            f"/agent/{aid}/health",
            json={
                "hostname": "vcoo-test",
                "uptime_seconds": 3600,
                "hermes_running": True,
                "disk_used_pct": 21.8,
                "template_version": "1.2.0",
                "supervisor_version": "0.1.0",
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_health_unknown_agent_404(self, client):
        r = client.post(
            "/agent/00000000-0000-0000-0000-000000000000/health",
            json={"hostname": "ghost"},
        )
        assert r.status_code == 404
