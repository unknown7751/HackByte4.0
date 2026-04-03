"""
Geospatial volunteer dispatch service.

Finds the nearest available volunteer to an accident using PostGIS
spatial queries and creates a task assignment.
"""

import logging
from uuid import UUID

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.accident import Accident
from src.models.volunteer import Volunteer
from src.models.task import Task

logger = logging.getLogger(__name__)


class DispatchService:
    """Handles proximity-based volunteer dispatch and task creation."""

    async def find_nearest_volunteer(
        self,
        db: AsyncSession,
        accident_id: UUID,
        max_distance_km: float = 50.0,
    ) -> Volunteer | None:
        """Find the nearest available volunteer to an accident.

        Uses PostGIS ST_Distance on geography cast for accurate distance
        in metres, then filters by max_distance_km.

        Args:
            db: Async database session
            accident_id: UUID of the accident to dispatch for
            max_distance_km: Maximum search radius in kilometres

        Returns:
            The nearest Volunteer, or None if no one is available.
        """
        # Get the accident location
        acc_result = await db.execute(
            select(Accident).where(Accident.id == accident_id)
        )
        accident = acc_result.scalar_one_or_none()
        if accident is None:
            logger.error("Accident %s not found", accident_id)
            return None

        if accident.location_geom is None:
            logger.warning("Accident %s has no location geometry", accident_id)
            return None

        max_distance_m = max_distance_km * 1000

        # PostGIS query: find nearest available volunteer within radius
        # ST_Distance on geography gives distance in metres
        distance_expr = func.ST_Distance(
            func.ST_GeogFromWKB(Volunteer.current_location),
            func.ST_GeogFromWKB(accident.location_geom),
        )

        query = (
            select(Volunteer, distance_expr.label("distance_m"))
            .where(
                Volunteer.is_available.is_(True),
                Volunteer.current_location.isnot(None),
                distance_expr <= max_distance_m,
            )
            .order_by(text("distance_m ASC"))
            .limit(1)
        )

        result = await db.execute(query)
        row = result.first()

        if row is None:
            logger.info(
                "No available volunteers within %.1f km of accident %s",
                max_distance_km, accident_id,
            )
            return None

        volunteer = row[0]
        distance = row[1]
        logger.info(
            "Nearest volunteer for accident %s: %s (%.1f m away)",
            accident_id, volunteer.id, distance,
        )
        return volunteer

    async def dispatch(
        self,
        db: AsyncSession,
        accident_id: UUID,
        max_distance_km: float = 50.0,
    ) -> Task | None:
        """Full dispatch: find nearest volunteer, create task, mark volunteer busy.

        Returns:
            Created Task, or None if no volunteer is available.
        """
        volunteer = await self.find_nearest_volunteer(db, accident_id, max_distance_km)
        if volunteer is None:
            return None

        # Create the task assignment
        task = Task(
            accident_id=accident_id,
            volunteer_id=volunteer.id,
            status="pending",
        )
        db.add(task)

        # Mark volunteer as unavailable
        volunteer.is_available = False

        await db.flush()
        await db.refresh(task)

        logger.info(
            "Dispatched volunteer %s to accident %s → task %s",
            volunteer.id, accident_id, task.id,
        )
        return task
