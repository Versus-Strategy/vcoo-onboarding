"""Tests de la siembra del primer operador (seed_first_operator).

Verifica que:
- Con FIRST_OPERATOR_* vacíos NO se crea un operador (evita cuentas inservibles
  con credenciales vacías).
- El fallback de email es admin@versus-strategy.com cuando la variable no existe.
- No pisa un operador existente (solo siembra si la tabla está vacía).
"""
import importlib

from db import SessionLocal
import crud


def _clear_operators():
    db = SessionLocal()
    try:
        for op in db.query(crud.models.Operator).all():
            db.delete(op)
        db.commit()
    finally:
        db.close()


def _count():
    db = SessionLocal()
    try:
        return crud.count_operators(db)
    finally:
        db.close()


def test_seed_skips_when_credentials_empty(monkeypatch):
    """Con FIRST_OPERATOR_EMAIL/PASSWORD vacíos, no se crea operador."""
    import main
    monkeypatch.setenv("FIRST_OPERATOR_EMAIL", "")
    monkeypatch.setenv("FIRST_OPERATOR_PASSWORD", "")
    _clear_operators()
    assert _count() == 0

    main.seed_first_operator()

    assert _count() == 0, "no debe crear operador con credenciales vacías"


def test_seed_uses_versus_email_fallback(monkeypatch):
    """Sin FIRST_OPERATOR_EMAIL, usa admin@versus-strategy.com."""
    import main
    monkeypatch.delenv("FIRST_OPERATOR_EMAIL", raising=False)
    monkeypatch.setenv("FIRST_OPERATOR_PASSWORD", "SomePass123")
    _clear_operators()

    main.seed_first_operator()

    db = SessionLocal()
    try:
        op = crud.get_operator_by_email(db, "admin@versus-strategy.com")
        assert op is not None, "debe sembrar con el fallback admin@versus-strategy.com"
    finally:
        db.close()


def test_seed_noop_when_operator_exists(monkeypatch):
    """Si ya hay un operador, no crea otro."""
    import main
    monkeypatch.setenv("FIRST_OPERATOR_EMAIL", "someone@example.com")
    monkeypatch.setenv("FIRST_OPERATOR_PASSWORD", "SomePass123")
    # reset_db (autouse) ya sembró admin@test.io -> hay 1 operador
    before = _count()
    assert before >= 1

    main.seed_first_operator()

    assert _count() == before, "no debe crear operador adicional si ya existe uno"
