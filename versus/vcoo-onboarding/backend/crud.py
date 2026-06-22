from sqlalchemy.orm import Session
from . import models


def create_vcoo(db: Session, name: str = None):
    v = models.VCOO(name=name)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def get_vcoo(db: Session, vcoo_id: str):
    return db.query(models.VCOO).filter(models.VCOO.id==vcoo_id).first()


def create_agent(db: Session, vcoo_id: str, info: str = None):
    a = models.Agent(vcoo_id=vcoo_id, info=info, status='online')
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def get_agent_by_vcoo(db: Session, vcoo_id: str):
    return db.query(models.Agent).filter(models.Agent.vcoo_id==vcoo_id).order_by(models.Agent.created_at.desc()).first()


def create_command(db: Session, agent_id: str, command: str):
    c = models.Command(agent_id=agent_id, command=command)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def get_pending_commands(db: Session, agent_id: str):
    return db.query(models.Command).filter(models.Command.agent_id==agent_id, models.Command.status=='pending').all()


def mark_command_sent(db: Session, command_id: str):
    db.query(models.Command).filter(models.Command.id==command_id).update({"status": "sent"})
    db.commit()
