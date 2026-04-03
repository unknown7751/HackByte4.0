import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from geoalchemy2 import Geometry
from .base import Base

class Accident(Base):
    __tablename__ = "accidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(String, nullable=False, index=True)  # e.g. "voice-+919876543210"
    
    # Description and reported details
    description = Column(String, nullable=True)
    location_name = Column(String, nullable=False)
    
    # Geocoded location (PostGIS)
    location_geom = Column(Geometry('POINT'), nullable=False)
    
    # Machine Learning assessed criticality: "Moderate", "Highly Critical"
    criticality = Column(String, nullable=True)
    
    # Auto-extracted assistance types from report
    assistance_required = Column(ARRAY(String), nullable=True)
    
    # Status: reported, assessing, dispatched, resolved
    status = Column(String, default="reported")
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
