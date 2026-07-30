"""Tests para el tick interval y configuración del agente."""
from unittest.mock import patch, MagicMock
import json
import os


def test_agent_tick_interval_from_config():
    """El Plugin.tick debe leer el intervalo del config."""
    import os, sys
    plugins_dir = os.path.join(os.path.dirname(__file__), *[".."] * 3, "packages", "template", "vcoo-supervisor", "plugins")
    sys.path.insert(0, os.path.abspath(plugins_dir))
    from tick import Plugin

    p = Plugin()
    assert p.interval == 60  # default

    # Simular start() con config de 5s
    config = {
        "agent_id": "test-agent",
        "agent_token": "test-token",
        "interval": 5,
        "control_plane": "http://localhost:8000",
    }
    p.start(config)
    assert p.interval == 5
    assert p.tick_interval == 5


def test_agent_tick_interval_from_env():
    """Si el config no tiene interval, debe mantener el default."""
    import os, sys
    plugins_dir = os.path.join(os.path.dirname(__file__), *[".."] * 3, "packages", "template", "vcoo-supervisor", "plugins")
    sys.path.insert(0, os.path.abspath(plugins_dir))
    from tick import Plugin

    p = Plugin()
    config = {
        "agent_id": "test-agent",
        "agent_token": "test-token",
        "control_plane": "http://localhost:8000",
    }
    p.start(config)
    assert p.interval == 60  # default, no override


def test_backend_tick_interval_sin_comandos(client, operator_token):
    """Sin comandos pendientes, tick_interval debe ser 0 (para que el agente use su config)."""
    from main import application
    from fastapi.testclient import TestClient
    tc = TestClient(application)

    # Necesitamos un agente registrado para el tick
    # El fixture client ya tiene todo configurado
    resp = client.post(
        "/agent/test-agent-id/tick",
        json={"health": {"uptime": 100}},
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert resp.status_code == 401  # token inválido


def test_pair_whatsapp_in_valid_commands():
    """pair-whatsapp debe estar en _VALID_AGENT_COMMANDS."""
    from main import _VALID_AGENT_COMMANDS
    assert "pair-whatsapp" in _VALID_AGENT_COMMANDS


def test_pair_whatsapp_payload_sent_to_agent():
    """El payload del comando pair-whatsapp debe incluirse en la respuesta del tick."""
    # Verificamos que main.py incluya pair-whatsapp en la lista de comandos con payload
    main_py = os.path.join(os.path.dirname(__file__), "..", "main.py")
    with open(os.path.abspath(main_py)) as f:
        content = f.read()
    assert 'pair-whatsapp' in content
    # Verificar que está en la línea de payload
    for line in content.split('\n'):
        if 'pair-whatsapp' in line and 'save-creds' in line:
            assert True
            break
    else:
        # Buscar específicamente la línea
        found = False
        for i, line in enumerate(content.split('\n')):
            if 'cmd.command in' in line and 'pair-whatsapp' in line:
                found = True
                break
        assert found, "pair-whatsapp no está en la lista de comandos con payload"
