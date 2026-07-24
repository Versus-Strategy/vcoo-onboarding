"""Tests para el flujo de emparejamiento de WhatsApp."""
import json


def _create_agent(vcoo_id: str):
    from db import SessionLocal
    from models import Agent
    db = SessionLocal()
    agent = Agent(vcoo_id=vcoo_id, status="online", encryption_key="test-key")
    db.add(agent)
    db.commit()
    aid = str(agent.id)
    db.close()
    return aid


def test_start_pair_whatsapp_creates_command(client, operator_token, make_vcoo):
    """POST /setup/{id}/start-pair-whatsapp debe crear un comando pair-whatsapp en el agente."""
    vcoo_id = make_vcoo()
    agent_id = _create_agent(vcoo_id)

    resp = client.post(
        f"/setup/{vcoo_id}/start-pair-whatsapp",
        json={"phone": "+521234567890"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "command_sent"
    assert data["mode"] == "pairing_code"

    from db import SessionLocal
    from models import Command
    db = SessionLocal()
    cmd = db.query(Command).filter(Command.id == data["cmd_id"]).first()
    assert cmd is not None
    assert cmd.command == "pair-whatsapp"
    assert cmd.agent_id == agent_id
    assert cmd.status == "pending"
    db.close()


def test_start_pair_whatsapp_qr_mode(client, operator_token, make_vcoo):
    """Sin phone, debe crear comando en modo QR."""
    vcoo_id = make_vcoo()
    _create_agent(vcoo_id)

    resp = client.post(
        f"/setup/{vcoo_id}/start-pair-whatsapp",
        json={},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "qr"


def test_start_pair_whatsapp_sin_agente(client, operator_token, make_vcoo):
    """Sin agente instalado, debe devolver error."""
    vcoo_id = make_vcoo()
    resp = client.post(
        f"/setup/{vcoo_id}/start-pair-whatsapp",
        json={"phone": "+521234567890"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 400
    assert "agent not installed" in resp.json()["detail"]


def test_whatsapp_qr_sin_comando(client, operator_token, make_vcoo):
    """Sin comandos previos, debe devolver no_command."""
    vcoo_id = make_vcoo()
    _create_agent(vcoo_id)

    resp = client.get(
        f"/setup/{vcoo_id}/whatsapp-qr",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "no_command"


def test_whatsapp_qr_devuelve_pairing_code(client, operator_token, make_vcoo):
    """Cuando el comando tiene resultado, debe devolver el código de emparejamiento."""
    vcoo_id = make_vcoo()
    agent_id = _create_agent(vcoo_id)

    from db import SessionLocal
    from models import Command
    db = SessionLocal()
    cmd = Command(
        agent_id=agent_id,
        command="pair-whatsapp",
        status="done",
        result=json.dumps({"output": "ABC12345", "mode": "pairing_code"}),
    )
    db.add(cmd)
    db.commit()
    db.close()

    resp = client.get(
        f"/setup/{vcoo_id}/whatsapp-qr",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pairing_code"
    assert data["code"] == "ABC12345"


def test_whatsapp_qr_devuelve_qr_data(client, operator_token, make_vcoo):
    """Cuando el comando tiene resultado QR, debe devolver el string QR."""
    vcoo_id = make_vcoo()
    agent_id = _create_agent(vcoo_id)

    from db import SessionLocal
    from models import Command
    db = SessionLocal()
    cmd = Command(
        agent_id=agent_id,
        command="pair-whatsapp",
        status="done",
        result=json.dumps({"output": "qrcode-data-string", "mode": "qr"}),
    )
    db.add(cmd)
    db.commit()
    db.close()

    resp = client.get(
        f"/setup/{vcoo_id}/whatsapp-qr",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "qr"
    assert data["qr"] == "qrcode-data-string"


def test_whatsapp_qr_pendiente(client, operator_token, make_vcoo):
    """Comando en estado pending debe devolver pending."""
    vcoo_id = make_vcoo()
    agent_id = _create_agent(vcoo_id)

    from db import SessionLocal
    from models import Command
    db = SessionLocal()
    cmd = Command(
        agent_id=agent_id,
        command="pair-whatsapp",
        status="pending",
    )
    db.add(cmd)
    db.commit()
    db.close()

    resp = client.get(
        f"/setup/{vcoo_id}/whatsapp-qr",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"
