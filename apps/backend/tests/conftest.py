"""Configuración compartida de pytest para el backend de vcoo-onboarding.

Establece las variables de entorno ANTES de importar la app (obligatorio, ya que
`db.py` y `auth.py` leen `POSTGRES_URL` y `MASTER_KEY` en el momento del import).

Expone fixtures reutilizables:
- ``client``            TestClient de FastAPI.
- ``db_session``        Sesión SQLAlchemy sobre la BD de test.
- ``reset_db``          (autouse) limpia todas las tablas y re-siembra el operador.
- ``operator_token``    JWT válido de operador ya autenticado.
- ``make_vcoo``         factory: crea un VCOO y devuelve su id.
- ``provision_token``   factory: devuelve el token de provision activo de un VCOO.
"""
import os
import sys

# ── Env vars: DEBEN establecerse antes de cualquier import de la app ──
DB_PATH = "/tmp/test_pytest.db"
os.environ.setdefault("POSTGRES_URL", f"sqlite:///{DB_PATH}")
os.environ.setdefault("MASTER_KEY", "pytest-key-12345")
os.environ.setdefault("SECRET_KEY", "pytest-secret-key")
os.environ.setdefault("FIRST_OPERATOR_EMAIL", "admin@test.io")
os.environ.setdefault("FIRST_OPERATOR_PASSWORD", "AdminPass1")
os.environ.setdefault("FIRST_OPERATOR_NAME", "Admin")
os.environ.setdefault("DASHBOARD_PASSWORD", "versus")
os.environ.setdefault("DASHBOARD_URL", "http://localhost:3000")
os.environ.setdefault("CONTROL_PLANE", "http://localhost:8000")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")

# Permitir importar los módulos de la app (main, crud, auth, ...) que viven en el
# directorio padre de tests/.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402
import models  # noqa: E402,F401
from db import engine, Base, SessionLocal  # noqa: E402

Base.metadata.create_all(bind=engine)

from fastapi.testclient import TestClient  # noqa: E402
from main import application  # noqa: E402
import crud  # noqa: E402
import auth as auth_mod  # noqa: E402

ADMIN_EMAIL = "admin@test.io"
ADMIN_PASSWORD = "AdminPass1"


@pytest.fixture(scope="session")
def client() -> TestClient:
    """TestClient de FastAPI compartido para toda la sesión."""
    return TestClient(application)


@pytest.fixture()
def db_session():
    """Sesión SQLAlchemy sobre la BD de test. Se cierra al terminar el test."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def reset_db():
    """Limpia todas las tablas y re-siembra el operador admin antes de cada test.

    También resetea el rate limiter para que los tests no interfieran entre sí.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    pw = auth_mod.hash_password(ADMIN_PASSWORD)
    crud.create_operator(db, email=ADMIN_EMAIL, password_hash=pw, name="Admin")
    db.commit()
    db.close()

    from ratelimit import _login_limiter
    _login_limiter._attempts.clear()
    yield


@pytest.fixture()
def operator_token(client: TestClient) -> str:
    """Devuelve un JWT válido de operador (login con el admin sembrado)."""
    r = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login operador falló: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture()
def make_vcoo(client: TestClient, operator_token: str):
    """Factory que crea un VCOO y devuelve su id.

    Uso: ``vcoo_id = make_vcoo("Nombre")``
    """
    def _make(name: str = "Test VCOO") -> str:
        r = client.post(
            "/vcoo",
            json={"name": name},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert r.status_code == 200, f"crear VCOO falló: {r.status_code} {r.text}"
        return r.json()["id"]

    return _make


@pytest.fixture()
def provision_token():
    """Factory que devuelve el token de provision activo (raw) de un VCOO."""
    def _token(vcoo_id: str) -> str:
        db = SessionLocal()
        try:
            pt = crud.get_active_token_for_vcoo(db, vcoo_id)
            assert pt is not None, f"no hay token activo para el VCOO {vcoo_id}"
            return pt.token
        finally:
            db.close()

    return _token
