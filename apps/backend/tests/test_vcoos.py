"""Tests de las operaciones sobre VCOOs (crear, listar, estado, tokens, borrar)."""


class TestVcoos:
    # ── Crear / listar ──

    def test_create_vcoo_returns_id_and_url(self, client, operator_token):
        r = client.post(
            "/vcoo",
            json={"name": "Acme Corp"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["id"]
        assert d["name"] == "Acme Corp"
        assert d["status"]
        assert d["modules"] == ["core"]
        assert "/setup/" in d["onboarding_url"]

    def test_create_vcoo_requires_auth(self, client):
        r = client.post("/vcoo", json={"name": "NoAuth"})
        assert r.status_code == 401

    def test_create_vcoo_with_modules(self, client, operator_token):
        r = client.post(
            "/vcoo",
            json={"name": "Multi", "modules": ["core", "google"]},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert r.status_code == 200
        assert r.json()["modules"] == ["core", "google"]

    def test_list_vcoos_requires_auth(self, client):
        r = client.get("/vcoos")
        assert r.status_code == 401

    def test_list_vcoos_includes_created(self, client, operator_token, make_vcoo):
        vid = make_vcoo("Listed")
        r = client.get("/vcoos", headers={"Authorization": f"Bearer {operator_token}"})
        assert r.status_code == 200
        ids = [v["id"] for v in r.json()]
        assert vid in ids

    # ── Estado ──

    def test_state_requires_auth(self, client, make_vcoo):
        vid = make_vcoo("StateNoAuth")
        r = client.get(f"/vcoo/{vid}/state")
        assert r.status_code == 401

    def test_state_returns_onboarding_fields(self, client, operator_token, make_vcoo):
        vid = make_vcoo("StateTest")
        r = client.get(
            f"/vcoo/{vid}/state",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["step"]
        assert "modules" in d
        assert "progress" in d
        assert d["progress"]["total"] >= 1

    def test_state_unknown_vcoo_404(self, client, operator_token):
        r = client.get(
            "/vcoo/00000000-0000-0000-0000-000000000000/state",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert r.status_code == 404

    # ── Provision token ──

    def test_get_provision_token(self, client, operator_token, make_vcoo):
        vid = make_vcoo("TokenTest")
        r = client.get(
            f"/vcoo/{vid}/provision-token",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["token"]
        assert "install_command" in d
        assert f"/setup/{vid}" in d["onboarding_url"]

    def test_get_provision_token_requires_auth(self, client, make_vcoo):
        vid = make_vcoo("TokenNoAuth")
        r = client.get(f"/vcoo/{vid}/provision-token")
        assert r.status_code == 401

    def test_regenerate_token_changes_value(self, client, operator_token, make_vcoo):
        vid = make_vcoo("Regen")
        first = client.get(
            f"/vcoo/{vid}/provision-token",
            headers={"Authorization": f"Bearer {operator_token}"},
        ).json()["token"]
        r = client.post(
            f"/vcoo/{vid}/regenerate-token",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert r.status_code == 200
        assert r.json()["token"] != first

    # ── Complete / reactivate ──

    def test_complete_vcoo(self, client, operator_token, make_vcoo):
        vid = make_vcoo("Complete")
        r = client.post(
            f"/vcoo/{vid}/complete",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    def test_complete_unknown_vcoo_404(self, client, operator_token):
        r = client.post(
            "/vcoo/00000000-0000-0000-0000-000000000000/complete",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert r.status_code == 404

    # ── Borrar ──

    def test_delete_requires_auth(self, client, make_vcoo):
        vid = make_vcoo("DelNoAuth")
        r = client.delete(f"/vcoo/{vid}")
        assert r.status_code == 401

    def test_delete_vcoo(self, client, operator_token, make_vcoo):
        vid = make_vcoo("DelOk")
        r = client.delete(
            f"/vcoo/{vid}",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "deleted"
        # Ya no debe existir
        r2 = client.get(
            f"/vcoo/{vid}/state",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert r2.status_code == 404

    def test_delete_unknown_vcoo_404(self, client, operator_token):
        r = client.delete(
            "/vcoo/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert r.status_code == 404
