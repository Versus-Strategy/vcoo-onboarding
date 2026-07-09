"""Tests del endpoint de salud /healthz.

El setup de entorno, la creación de tablas y los fixtures compartidos viven en
conftest.py. Con la BD de test viva, /healthz debe reportar el estado real de la
base de datos (db: ok) y devolver 200.
"""
from fastapi.testclient import TestClient

from main import application

client = TestClient(application)


def test_healthz_ok_reports_db_ok():
    """Con la BD de test accesible, /healthz devuelve 200 y db='ok'."""
    r = client.get("/healthz")
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    body = r.json()
    assert body["status"] == "ok"
    # El healthcheck debe comprobar la BD, no solo devolver ok a ciegas.
    assert body["db"] == "ok", f"healthz no reporta estado real de BD: {body}"


def test_healthz_includes_version():
    """/healthz conserva metadatos útiles (version, python)."""
    r = client.get("/healthz")
    body = r.json()
    assert body.get("version") == "v2"
    assert "python" in body
