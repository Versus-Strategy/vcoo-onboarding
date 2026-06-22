from sqlalchemy.orm import Session
from . import models
from datetime import datetime, timedelta


def create_vcoo(db: Session, name: str = None):
    v = models.VCOO(name=name)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def get_vcoo(db: Session, vcoo_id: str):
    return db.query(models.VCOO).filter(models.VCOO.id == vcoo_id).first()


def list_vcoos(db: Session, limit: int = 50):
    """List VCOOs with their latest agent, ordered by creation date."""
    from sqlalchemy.orm import joinedload
    vcoos = (
        db.query(models.VCOO)
        .order_by(models.VCOO.created_at.desc())
        .limit(limit)
        .all()
    )
    # Attach latest agent for each VCOO
    for v in vcoos:
        agent = get_agent_by_vcoo(db, str(v.id))
        v.agent = agent  # attach dynamically
    return vcoos


# Agent CRUD
def create_agent(db: Session, vcoo_id: str, info: str = None):
    a = models.Agent(vcoo_id=vcoo_id, info=info, status='online')
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def set_agent_token_jti(db: Session, agent_id: str, jti: str):
    db.query(models.Agent).filter(models.Agent.id == agent_id).update({"token_jti": jti})
    db.commit()


def get_agent_by_vcoo(db: Session, vcoo_id: str):
    return db.query(models.Agent).filter(models.Agent.vcoo_id == vcoo_id).order_by(models.Agent.last_seen.desc()).first()


def get_agent(db: Session, agent_id: str):
    return db.query(models.Agent).filter(models.Agent.id == agent_id).first()


# Commands
def create_command(db: Session, agent_id: str, command: str):
    c = models.Command(agent_id=agent_id, command=command)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def get_pending_commands(db: Session, agent_id: str):
    return db.query(models.Command).filter(models.Command.agent_id == agent_id, models.Command.status == 'pending').all()


def mark_command_sent(db: Session, command_id: str):
    db.query(models.Command).filter(models.Command.id == command_id).update({"status": "sent"})
    db.commit()


def mark_command_done(db: Session, command_id: str, result: str = ''):
    db.query(models.Command).filter(models.Command.id == command_id).update({"status": "done", "result": result})
    db.commit()


def touch_agent(db: Session, agent_id: str):
    import datetime as dt
    db.query(models.Agent).filter(models.Agent.id == agent_id).update({"last_seen": dt.datetime.utcnow(), "status": "online"})
    db.commit()


# Provision tokens stored server-side to avoid reliance on process-local MASTER_KEY

def create_provision_for_vcoo(db: Session, vcoo_id: str, expires_minutes: int = 60):
    from . import auth
    token = auth.create_provision_token(vcoo_id, expires_minutes)
    expires_at = datetime.utcnow() + timedelta(minutes=expires_minutes)
    pt = models.ProvisionToken(token=token, vcoo_id=vcoo_id, expires_at=expires_at)
    db.add(pt)
    db.commit()
    return token


def validate_provision_token(db: Session, token: str):
    pt = db.query(models.ProvisionToken).filter(models.ProvisionToken.token == token).first()
    if not pt:
        return None
    if pt.used:
        return None
    if pt.expires_at and pt.expires_at.replace(tzinfo=None) < datetime.utcnow():
        return None
    # mark used and return vcoo_id
    pt.used = True
    db.commit()
    return str(pt.vcoo_id)


# Command logs persistence

def append_command_log(db: Session, command_id: str, chunk: str, stream: str = 'stdout'):
    cl = models.CommandLog(command_id=command_id, chunk=chunk, stream=stream)
    db.add(cl)
    db.commit()
    return cl
