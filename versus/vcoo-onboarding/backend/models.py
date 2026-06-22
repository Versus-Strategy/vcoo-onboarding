from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from .db import Base

class VCOO(Base):
    __tablename__ = 'vcoos'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    integrations = Column(String, nullable=True)  # JSON string placeholder

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "integrations": self.integrations,
        }

class Agent(Base):
    __tablename__ = 'agents'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vcoo_id = Column(UUID(as_uuid=True), nullable=False)
    info = Column(String, nullable=True)
    last_seen = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default='offline')
    token_jti = Column(String, nullable=True)  # for revocation reference

    def to_dict(self):
        return {
            "id": str(self.id),
            "vcoo_id": str(self.vcoo_id),
            "info": self.info,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "status": self.status,
        }

class Command(Base):
    __tablename__ = 'commands'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), nullable=False)
    command = Column(String, nullable=False)
    status = Column(String, default='pending')
    result = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
