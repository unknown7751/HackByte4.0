"""Pydantic schemas for the Accident entity."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Shared sub-models ──────────────────────────────────────────
class LatLng(BaseModel):
    """Latitude / longitude pair used for API input/output."""
    lat: float = Field(..., ge=-90, le=90, examples=[21.1458])
    lng: float = Field(..., ge=-180, le=180, examples=[79.0882])


# ── Create ─────────────────────────────────────────────────────
class AccidentCreate(BaseModel):
    source_id: str = Field(..., min_length=1, examples=["voice-+919876543210"])
    description: str | None = None
    location_name: str = Field(..., min_length=1, examples=["Civil Lines, Nagpur"])
    location: LatLng
    criticality: str | None = Field(None, examples=["Moderate", "Highly Critical"])
    assistance_required: list[str] | None = Field(None, examples=[["ambulance", "fire_truck"]])
    status: str = Field("reported", examples=["reported"])


# ── Read (response) ───────────────────────────────────────────
class AccidentRead(BaseModel):
    id: UUID
    source_id: str
    description: str | None = None
    location_name: str
    location: LatLng | None = None
    criticality: str | None = None
    assistance_required: list[str] | None = None
    status: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Update (partial) ──────────────────────────────────────────
class AccidentUpdate(BaseModel):
    description: str | None = None
    location_name: str | None = None
    location: LatLng | None = None
    criticality: str | None = None
    assistance_required: list[str] | None = None
    status: str | None = None


# ── List wrapper ───────────────────────────────────────────────
class AccidentList(BaseModel):
    total: int
    items: list[AccidentRead]
