from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from .db import Base

class VCOO(Base):
    __tablename__ = 'vcoos'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=True)
    status = Column(String, default='active')  # 'active' | 'completed'
    created_at = Column(DateTime, default=datetime.utcnow)
    integrations = Column(String, nullable=True)  # JSON string placeholder

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "status": self.status,
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
    command = Column(Text, nullable=False)
    status = Column(String, default='pending')
    result = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # SPEC v2: onboarding fields
    step = Column(String, nullable=True)
    ttl_seconds = Column(Integer, default=300)
    sent_at = Column(DateTime, nullable=True)
    acked = Column(Boolean, default=False)

class CommandLog(Base):
    __tablename__ = 'command_logs'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    command_id = Column(UUID(as_uuid=True), ForeignKey('commands.id'), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    stream = Column(String, default='stdout')
    chunk = Column(Text, nullable=False)

class ProvisionToken(Base):
    __tablename__ = 'provision_tokens'
    token = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    vcoo_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    used = Column(Boolean, default=False)


class OnboardingState(Base):
    """SPEC v2 §3.2: tracks onboarding wizard progress per VCOO."""
    __tablename__ = 'onboarding_state'

    vcoo_id = Column(UUID(as_uuid=True), ForeignKey('vcoos.id', ondelete='CASCADE'),
                     primary_key=True)
    step = Column(String, nullable=False, default='bootstrap')
    # bootstrap | google-oauth | trello-setup | github-setup |
    # vercel-setup | supabase-setup | gmail-setup | finalize | done

    status = Column(String, nullable=False, default='in_progress')
    # in_progress | blocked | completed

    modules = Column(JSON, nullable=False, default=list)
    # ["core", "office", "mail", "planner", "developer"]

    completed = Column(JSON, nullable=False, default=list)
    # ["bootstrap", "google-oauth"]

    errors = Column(JSON, nullable=False, default=list)
    # [{"step": "google-oauth", "error": "...", "timestamp": "..."}]

    retry_count = Column(JSON, nullable=False, default=dict)
    # {"google-oauth": 2}

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationship
    vcoo = relationship("VCOO", backref="onboarding_state", uselist=False)
