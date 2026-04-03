"""
Trello Webhook endpoint — the main ingestion pipeline.

Flow:
  1. Trello sends POST with card data
  2. Parse card → extract accident details
  3. Fetch full card details (labels, checklists) from Trello API
  4. Geocode the location
  5. Predict criticality via ML
  6. Store the accident
  7. Dispatch nearest volunteer
  8. Return the result
"""

import logging

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database import get_db
from src.models.accident import Accident
from src.services.trello import TrelloService
from src.services.geocoding import GeocodingService
from src.services.ml_predictor import MLPredictor
from src.services.dispatch import DispatchService
from src.utils import latlng_to_wkb

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# Instantiate services
trello_svc = TrelloService()
geocoding_svc = GeocodingService()
ml_predictor = MLPredictor()
dispatch_svc = DispatchService()


@router.head("/trello")
async def trello_webhook_verify():
    """Trello sends a HEAD request to verify the webhook URL exists.

    Must return 200 for Trello to consider the webhook valid.
    """
    return Response(status_code=status.HTTP_200_OK)


@router.post("/trello")
async def trello_webhook_receive(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive and process a Trello webhook event.

    This is the main ingestion pipeline:
      Card created on Trello → Parse → Geocode → ML Predict → Store → Dispatch
    """
    try:
        payload = await request.json()
    except Exception:
        logger.warning("Invalid JSON in Trello webhook payload")
        return {"status": "ignored", "reason": "invalid payload"}

    # ── Step 1: Parse the webhook payload ──────────────────────
    report = trello_svc.parse_webhook_payload(payload)
    if report is None:
        return {"status": "ignored", "reason": "not a card creation/update event"}

    logger.info(
        "Processing Trello card: %s — location: '%s'",
        report.trello_card_id, report.location_name,
    )

    # ── Step 2: Fetch full card details for richer data ────────
    card_data = await trello_svc.fetch_card_details(report.trello_card_id)
    if card_data:
        # Enrich assistance list from checklists
        checklist_items = TrelloService.extract_checklist_items(card_data)
        if checklist_items:
            existing = report.assistance_required or []
            report.assistance_required = list(set(existing + checklist_items))

        # Get labels if not already parsed (webhook payload sometimes lacks them)
        if not report.criticality_hint and card_data.get("labels"):
            for label in card_data["labels"]:
                color = (label.get("color") or "").lower()
                if color in ("red", "orange"):
                    report.criticality_hint = "Highly Critical"
                    break
                elif color in ("yellow", "green"):
                    report.criticality_hint = "Moderate"

    # ── Step 3: Geocode the location ──────────────────────────
    latlng = await geocoding_svc.geocode(report.location_name)
    location_geom = latlng_to_wkb(latlng) if latlng else None

    if location_geom is None:
        # Fallback: use a default point (0,0) — or skip spatial features
        logger.warning(
            "Could not geocode '%s' — storing without geometry",
            report.location_name,
        )
        from src.schemas.accident import LatLng
        # Use 0,0 as fallback so PostGIS NOT NULL constraint is satisfied
        fallback = LatLng(lat=0.0, lng=0.0)
        location_geom = latlng_to_wkb(fallback)

    # ── Step 4: ML criticality prediction ─────────────────────
    # Use label hint from Trello if available, else predict via ML
    ml_info = None
    if report.criticality_hint:
        criticality = report.criticality_hint
        ml_info = {"prediction": criticality, "confidence": 1.0, "method": "trello_label"}
    else:
        ml_result = ml_predictor.predict_with_confidence(
            description=report.description,
            assistance_required=report.assistance_required,
            location_name=report.location_name,
        )
        criticality = ml_result["prediction"]
        ml_info = ml_result

    # ── Step 5: Store the accident ────────────────────────────
    accident = Accident(
        trello_card_id=report.trello_card_id,
        description=report.description,
        location_name=report.location_name,
        location_geom=location_geom,
        criticality=criticality,
        assistance_required=report.assistance_required,
        status="reported",
    )
    db.add(accident)
    await db.flush()
    await db.refresh(accident)

    logger.info(
        "Accident stored: id=%s, criticality=%s, location='%s'",
        accident.id, criticality, report.location_name,
    )

    # ── Step 6: Auto-dispatch nearest volunteer ───────────────
    task = await dispatch_svc.dispatch(db, accident.id)
    dispatch_info = None
    if task:
        accident.status = "dispatched"
        dispatch_info = {
            "task_id": str(task.id),
            "volunteer_id": str(task.volunteer_id),
            "status": task.status,
        }
        logger.info("Volunteer dispatched: task=%s", task.id)
    else:
        accident.status = "assessing"
        logger.info("No volunteers available — accident %s awaiting dispatch", accident.id)

    await db.flush()

    return {
        "status": "processed",
        "accident_id": str(accident.id),
        "criticality": criticality,
        "ml_prediction": ml_info,
        "location_name": report.location_name,
        "geocoded": latlng is not None,
        "dispatch": dispatch_info,
    }
