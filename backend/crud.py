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
