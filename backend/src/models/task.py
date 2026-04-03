import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .base import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    accident_id = Column(UUID(as_uuid=True), ForeignKey("accidents.id"), nullable=False)
    volunteer_id = Column(UUID(as_uuid=True), ForeignKey("volunteers.id"), nullable=False)
    
    # Task Status: pending, accepted, in-progress, completed, verified
    status = Column(String, default="pending")
    
    assigned_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Blockchain transaction details
    reward_tx_hash = Column(String, nullable=True)

    # Relationships
    accident = relationship("Accident", backref="tasks")
    volunteer = relationship("Volunteer", backref="tasks")
