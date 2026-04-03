"""
Voice call endpoints for accident reporting via Twilio.

Call Flow:
  1. Caller dials Twilio number
  2. Twilio sends POST to /api/v1/voice/incoming
  3. Backend asks for location → caller speaks
  4. Twilio transcribes → POST to /api/v1/voice/location
  5. Backend asks for description → caller speaks
  6. Twilio transcribes → POST to /api/v1/voice/report
  7. Backend processes: geocode → ML predict → store → dispatch
  8. Backend reads back confirmation to caller
"""

import logging

from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database import get_db
from src.models.accident import Accident
from src.services.twilio_voice import VoiceService
from src.services.geocoding import GeocodingService
from src.services.ml_predictor import MLPredictor
from src.services.dispatch import DispatchService
from src.utils import latlng_to_wkb
from src.schemas.accident import LatLng

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice Calls"])

# Instantiate services
voice_svc = VoiceService()
geocoding_svc = GeocodingService()
ml_predictor = MLPredictor()
dispatch_svc = DispatchService()


def twiml_response(twiml: str) -> FastAPIResponse:
    """Wrap TwiML string in a proper XML response."""
    return FastAPIResponse(content=twiml, media_type="application/xml")


# ── Step 1: Incoming call ──────────────────────────────────────
@router.post("/incoming")
async def voice_incoming(request: Request):
    """Handle an incoming voice call from Twilio.

    This is the first endpoint Twilio hits when someone calls.
    Responds with TwiML that greets the caller and asks for location.
    """
    form = await request.form()
    caller = form.get("From", "unknown")
    logger.info("📞 Incoming call from: %s", caller)

    twiml = voice_svc.greeting_response()
    return twiml_response(twiml)


# ── Step 2: Location received ─────────────────────────────────
@router.post("/location")
async def voice_location(
    request: Request,
    SpeechResult: str = Form(default=""),
    Confidence: float = Form(default=0.0),
):
    """Process the transcribed location from the caller.

    Twilio sends the speech-to-text result here.
    We acknowledge the location and ask for accident details.
    """
    location = SpeechResult.strip()

    if not location:
        logger.warning("No speech detected for location")
        location = "Unknown location"

    logger.info(
        "📍 Location received: '%s' (confidence: %.2f)",
        location, Confidence,
    )

    twiml = voice_svc.ask_for_description(location)
    return twiml_response(twiml)


# ── Step 3: Full report received — process pipeline ───────────
@router.post("/report")
async def voice_report(
    request: Request,
    location: str = Query(default="Unknown location"),
    SpeechResult: str = Form(default=""),
    Confidence: float = Form(default=0.0),
    db: AsyncSession = Depends(get_db),
):
    """Process the full accident report from the caller.

    This is the main pipeline — same as the old webhook but triggered by voice:
      Speech → Geocode → ML Predict → Store → Dispatch → Voice confirmation
    """
    description = SpeechResult.strip()
    form = await request.form()
    caller = form.get("From", "unknown")

    if not description:
        description = "Accident reported via phone call. No details provided."

    logger.info(
        "📝 Report from %s: location='%s', description='%s' (confidence: %.2f)",
        caller, location, description[:80], Confidence,
    )

    # ── Geocode the location ──────────────────────────────────
    latlng = await geocoding_svc.geocode(location)
    location_geom = latlng_to_wkb(latlng) if latlng else None

    if location_geom is None:
        logger.warning("Could not geocode '%s' — storing with fallback", location)
        fallback = LatLng(lat=0.0, lng=0.0)
        location_geom = latlng_to_wkb(fallback)

    # ── ML criticality prediction ─────────────────────────────
    assistance = voice_svc.extract_assistance_from_speech(description)
    ml_result = ml_predictor.predict_with_confidence(
        description=description,
        assistance_required=assistance,
        location_name=location,
    )
    criticality = ml_result["prediction"]

    import time
    source_id = f"voice-{caller}-{int(time.time())}"

    # ── Store the accident ────────────────────────────────────
    accident = Accident(
        source_id=source_id,
        description=description,
        location_name=location,
        location_geom=location_geom,
        criticality=criticality,
        assistance_required=assistance,
        status="reported",
    )
    db.add(accident)
    await db.flush()
    await db.refresh(accident)

    logger.info(
        "✅ Accident stored: id=%s, criticality=%s, from=%s",
        accident.id, criticality, caller,
    )

    # ── Auto-dispatch nearest volunteer ───────────────────────
    task = await dispatch_svc.dispatch(db, accident.id)
    volunteer_dispatched = task is not None

    if task:
        accident.status = "dispatched"
        logger.info("🚨 Volunteer dispatched: task=%s", task.id)
    else:
        accident.status = "assessing"
        logger.info("⏳ No volunteers nearby — awaiting dispatch")

    await db.flush()

    # ── Speak confirmation back to caller ─────────────────────
    twiml = voice_svc.report_confirmation(
        criticality=criticality,
        accident_id=str(accident.id),
        volunteer_dispatched=volunteer_dispatched,
    )
    return twiml_response(twiml)


# ── Status callback (optional — Twilio calls this when call ends)
@router.post("/status")
async def voice_status(request: Request):
    """Handle Twilio call status callbacks (optional logging)."""
    form = await request.form()
    call_sid = form.get("CallSid", "")
    call_status = form.get("CallStatus", "")
    duration = form.get("CallDuration", "0")

    logger.info(
        "📱 Call %s status: %s (duration: %ss)",
        call_sid[:12], call_status, duration,
    )
    return {"status": "ok"}
