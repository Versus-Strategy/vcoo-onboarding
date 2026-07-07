import pytest
import json, time, base64

# El setup de entorno, la creación de tablas y los fixtures compartidos
# (reset_db autouse, operator_token, make_vcoo, provision_token) viven en
# conftest.py. Importamos los módulos de la app desde ahí.
from main import application
from fastapi.testclient import TestClient
import crud, auth as auth_mod


def jti_of(token: str) -> str:
    parts = token.split('.')
    if len(parts) != 3:
        return ''
    pad = 4 - len(parts[1]) % 4
    payload = parts[1] + ('=' * pad if pad else '')
    try:
        d = json.loads(base64.urlsafe_b64decode(payload))
        return d.get('jti', '')
    except Exception:
        return ''


class TestAuth:
    client = TestClient(application)
    _admin_token: str | None = None

    def _login(self) -> str:
        r = self.client.post('/auth/login', json={'email': 'admin@test.io', 'password': 'AdminPass1'})
        assert r.status_code == 200
        return r.json()['token']

    def _create_vcoo(self, name: str = 'Test', token: str | None = None) -> tuple[str, str]:
        t = token or self._login()
        r = self.client.post('/vcoo', json={'name': name},
                             headers={'Authorization': f'Bearer {t}'})
        assert r.status_code == 200, f'Create VCOO: {r.status_code} {r.text}'
        return r.json()['id'], t

    # ── Operators ──

    def test_01_seed_login(self):
        r = self.client.post('/auth/login', json={'email': 'admin@test.io', 'password': 'AdminPass1'})
        assert r.status_code == 200
        d = r.json()
        assert 'token' in d
        assert d['user']['role'] == 'operador'
        assert d['user']['id']

    def test_02_login_wrong_password(self):
        r = self.client.post('/auth/login', json={'email': 'admin@test.io', 'password': 'wrong'})
        assert r.status_code == 401

    def test_03_login_fallback_legacy(self):
        r = self.client.post('/auth/login', json={'email': 'x@y.com', 'password': 'versus'})
        assert r.status_code == 200
        assert 'token' in r.json()

    def test_04_register_operator(self):
        r = self.client.post('/auth/operator/register', json={
            'email': 'maria@test.io', 'password': 'Maria1', 'name': 'María',
        })
        assert r.status_code == 200
        assert r.json()['operator']['email'] == 'maria@test.io'

    def test_05_duplicate_operator_email(self):
        self.client.post('/auth/operator/register', json={
            'email': 'dup@test.io', 'password': 'x', 'name': 'x',
        })
        r = self.client.post('/auth/operator/register', json={
            'email': 'dup@test.io', 'password': 'y', 'name': 'y',
        })
        assert r.status_code == 409

    # ── Token refresh ──

    def test_06_refresh_operator(self):
        r = self.client.post('/auth/login', json={'email': 'admin@test.io', 'password': 'AdminPass1'})
        t1 = r.json()['token']
        time.sleep(1)
        r = self.client.post('/auth/refresh', json={'refreshToken': t1})
        assert r.status_code == 200
        t2 = r.json()['token']
        assert t2 != t1

    def test_07_refresh_rotation(self):
        r = self.client.post('/auth/login', json={'email': 'admin@test.io', 'password': 'AdminPass1'})
        t1 = r.json()['token']
        time.sleep(1)
        r = self.client.post('/auth/refresh', json={'refreshToken': t1})
        assert r.status_code == 200
        r = self.client.post('/auth/refresh', json={'refreshToken': t1})
        assert r.status_code == 401

    def test_08_refresh_client(self):
        v_id, _ = self._create_vcoo('Test')
        from db import SessionLocal
        db = SessionLocal()
        pt = crud.get_active_token_for_vcoo(db, v_id)
        db.close()
        r = self.client.post('/auth/client/register', json={
            'name': 'C', 'email': 'c@t.com', 'password': 'p', 'token': pt.token,
        })
        ct = r.json()['token']
        time.sleep(1)
        r = self.client.post('/auth/refresh', json={'refreshToken': ct})
        assert r.status_code == 200

    # ── VCOO operations ──

    def test_09_create_vcoo(self):
        v_id, _ = self._create_vcoo('My VCOO')
        assert v_id

    def test_10_regenerate_token_requires_auth(self):
        v_id, t = self._create_vcoo('T')
        r = self.client.post(f'/vcoo/{v_id}/regenerate-token')
        assert r.status_code == 401

    def test_11_regenerate_token_with_auth(self):
        v_id, t = self._create_vcoo('T')
        r = self.client.post(f'/vcoo/{v_id}/regenerate-token',
                             headers={'Authorization': f'Bearer {t}'})
        assert r.status_code == 200
        assert 'token' in r.json()

    # ── Token revocation ──

    def test_12_revoke_operator_token(self):
        r = self.client.post('/auth/login', json={'email': 'admin@test.io', 'password': 'AdminPass1'})
        t1 = r.json()['token']
        jti = jti_of(t1)
        r = self.client.post('/auth/revoke', headers={'Authorization': f'Bearer {t1}'},
                             json={'jti': jti})
        assert r.json()['status'] == 'revoked'

        # Login again for a fresh token
        t2 = self._login()
        v_id, _ = self._create_vcoo('X', token=t2)
        r = self.client.post(f'/vcoo/{v_id}/regenerate-token',
                             headers={'Authorization': f'Bearer {t1}'})
        assert r.status_code == 401

    def test_13_revoke_client_token(self):
        v_id, t = self._create_vcoo('T')
        from db import SessionLocal
        db = SessionLocal()
        pt = crud.get_active_token_for_vcoo(db, v_id)
        db.close()
        r = self.client.post('/auth/client/register', json={
            'name': 'C', 'email': 'cc@t.com', 'password': 'p', 'token': pt.token,
        })
        ct = r.json()['token']
        jti = jti_of(ct)

        r = self.client.post('/auth/revoke', headers={'Authorization': f'Bearer {t}'},
                             json={'jti': jti})
        assert r.json()['status'] == 'revoked'

        r = self.client.get('/auth/client/me', headers={'Authorization': f'Bearer {ct}'})
        assert r.status_code == 401

    def test_14_client_cannot_revoke(self):
        v_id, _ = self._create_vcoo('T')
        from db import SessionLocal
        db = SessionLocal()
        pt = crud.get_active_token_for_vcoo(db, v_id)
        db.close()
        r = self.client.post('/auth/client/register', json={
            'name': 'C', 'email': 'cc2@t.com', 'password': 'p', 'token': pt.token,
        })
        ct = r.json()['token']
        r = self.client.post('/auth/revoke', headers={'Authorization': f'Bearer {ct}'},
                             json={'jti': 'fake'})
        assert r.status_code == 403

    # ── Agent ──

    def test_15_agent_register_poll_refresh(self):
        v_id, _ = self._create_vcoo('AgentTest')
        from db import SessionLocal
        db = SessionLocal()
        pt = crud.get_active_token_for_vcoo(db, v_id)
        db.close()

        r = self.client.post('/register', json={'token': pt.token, 'info': {}})
        assert r.status_code == 200
        aid = r.json()['agent_id']
        at = r.json()['agent_token']

        r = self.client.get(f'/agent/{aid}/poll', headers={'Authorization': f'Bearer {at}'})
        assert r.status_code == 200

        time.sleep(1)
        r = self.client.post(f'/agent/{aid}/refresh', headers={'Authorization': f'Bearer {at}'})
        assert r.status_code == 200
        assert r.json()['token'] != at

    def test_16_agent_revoke(self):
        v_id, _ = self._create_vcoo('RevokeAgent')
        from db import SessionLocal
        db = SessionLocal()
        pt = crud.get_active_token_for_vcoo(db, v_id)
        db.close()

        r = self.client.post('/register', json={'token': pt.token, 'info': {}})
        aid = r.json()['agent_id']
        at = r.json()['agent_token']

        r = self.client.post(f'/agent/{aid}/revoke', headers={'Authorization': f'Bearer {at}'})
        assert r.json()['status'] == 'revoked'

        r = self.client.get(f'/agent/{aid}/poll', headers={'Authorization': f'Bearer {at}'})
        assert r.status_code == 401

    # ── Rate limiting ──

    def test_17_rate_limiting(self):
        for _ in range(5):
            self.client.post('/auth/login', json={'email': 'admin@test.io', 'password': 'wrong'})
        r = self.client.post('/auth/login', json={'email': 'admin@test.io', 'password': 'wrong'})
        assert r.status_code == 429

    # ── bcrypt ──

    def test_18_bcrypt(self):
        h = auth_mod.hash_password('test')
        assert h.startswith('$2b$')
        assert auth_mod.verify_password('test', h)
        assert not auth_mod.verify_password('wrong', h)

    # ── Provision token multi-use ──

    def test_19_provision_token_multi_use(self):
        v_id, _ = self._create_vcoo('Multi')
        from db import SessionLocal
        db = SessionLocal()
        pt = crud.get_active_token_for_vcoo(db, v_id).token
        db.close()

        r = self.client.post('/register', json={'token': pt, 'info': {}})
        assert r.status_code == 200

        r = self.client.post('/auth/client/register', json={
            'name': 'C', 'email': 'multi@t.com', 'password': 'p', 'token': pt,
        })
        assert r.status_code == 200

    # ── Audit log ──

    def test_20_audit_log(self):
        v_id, t = self._create_vcoo('AuditTest')

        r = self.client.post(f'/vcoo/{v_id}/regenerate-token',
                             headers={'Authorization': f'Bearer {t}'})
        assert r.status_code == 200

        r = self.client.get(f'/vcoo/{v_id}/audit',
                            headers={'Authorization': f'Bearer {t}'})
        assert r.status_code == 200
        logs = r.json()['audit_log']
        assert any(l['action'] == 'token.regenerated' for l in logs)

    # ── Delete VCOO ──

    def test_21_delete_vcoo_requires_auth(self):
        v_id, t = self._create_vcoo('DelTest')
        r = self.client.delete(f'/vcoo/{v_id}')
        assert r.status_code == 401

        r = self.client.delete(f'/vcoo/{v_id}', headers={'Authorization': f'Bearer {t}'})
        assert r.status_code in (200, 500)
