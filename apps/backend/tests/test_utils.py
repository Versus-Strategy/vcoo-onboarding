"""Tests de endpoints de utilidad: /healthz, /playbooks, /install.sh."""


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

    def test_install_sh_served(self, client):
        r = client.get("/install.sh")
        assert r.status_code == 200
        # Debe devolver texto (script bash o python)
        assert len(r.text) > 0
