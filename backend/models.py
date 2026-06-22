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
