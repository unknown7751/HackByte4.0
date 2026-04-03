"""CRUD routes for Accidents."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database import get_db
from src.models.accident import Accident
from src.schemas.accident import (
    AccidentCreate,
    AccidentRead,
    AccidentUpdate,
    AccidentList,
)
from src.utils import latlng_to_wkb, geom_to_latlng

router = APIRouter(prefix="/accidents", tags=["Accidents"])


def _row_to_schema(row: Accident) -> AccidentRead:
    """Convert an ORM Accident row to the Pydantic read schema."""
    return AccidentRead(
        id=row.id,
        source_id=row.source_id,
        description=row.description,
        location_name=row.location_name,
        location=geom_to_latlng(row.location_geom),
        criticality=row.criticality,
        assistance_required=row.assistance_required,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/", response_model=AccidentList)
async def list_accidents(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all accidents with pagination."""
    total_result = await db.execute(select(func.count(Accident.id)))
    total = total_result.scalar_one()

    result = await db.execute(
        select(Accident)
        .order_by(Accident.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = result.scalars().all()
    return AccidentList(total=total, items=[_row_to_schema(r) for r in rows])


@router.get("/{accident_id}", response_model=AccidentRead)
async def get_accident(
    accident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single accident by ID."""
    result = await db.execute(select(Accident).where(Accident.id == accident_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Accident not found")
    return _row_to_schema(row)


@router.post("/", response_model=AccidentRead, status_code=status.HTTP_201_CREATED)
async def create_accident(
    body: AccidentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new accident record."""
    accident = Accident(
        source_id=body.source_id,
        description=body.description,
        location_name=body.location_name,
        location_geom=latlng_to_wkb(body.location),
        criticality=body.criticality,
        assistance_required=body.assistance_required,
        status=body.status,
    )
    db.add(accident)
    await db.flush()
    await db.refresh(accident)
    return _row_to_schema(accident)


@router.patch("/{accident_id}", response_model=AccidentRead)
async def update_accident(
    accident_id: UUID,
    body: AccidentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Partially update an accident."""
    result = await db.execute(select(Accident).where(Accident.id == accident_id))
    accident = result.scalar_one_or_none()
    if accident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Accident not found")

    update_data = body.model_dump(exclude_unset=True)
    if "location" in update_data and update_data["location"] is not None:
        from src.schemas.accident import LatLng
        accident.location_geom = latlng_to_wkb(LatLng(**update_data.pop("location")))
    elif "location" in update_data:
        update_data.pop("location")

    for field, value in update_data.items():
        setattr(accident, field, value)

    await db.flush()
    await db.refresh(accident)
    return _row_to_schema(accident)


@router.delete("/{accident_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_accident(
    accident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete an accident by ID."""
    result = await db.execute(select(Accident).where(Accident.id == accident_id))
    accident = result.scalar_one_or_none()
    if accident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Accident not found")
    await db.delete(accident)
