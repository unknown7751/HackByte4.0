"""
Twilio Voice Call service for accident reporting.

Handles:
- Generating TwiML responses for interactive voice calls
- Processing speech transcriptions from callers
- Extracting accident details (location, description) from speech
"""

import logging
import re

from twilio.twiml.voice_response import VoiceResponse, Gather

from src.config.settings import settings

logger = logging.getLogger(__name__)


class VoiceService:
    """Generates TwiML responses for the voice call flow."""

    # ── Step 1: Greet the caller and ask for location ──────────
    @staticmethod
    def greeting_response() -> str:
        """Generate TwiML to greet caller and ask for accident location.

        Call flow:
          1. Greet → ask for location
          2. Caller speaks location
          3. Twilio transcribes and sends to /voice/location
        """
        response = VoiceResponse()
        response.say(
            "Welcome to Smart Accident Response System. "
            "Please describe the location of the accident after the beep.",
            voice="Polly.Aditi",
            language="en-IN",
        )

        gather = Gather(
            input="speech",
            action="/api/v1/voice/location",
            method="POST",
            timeout=5,
            speech_timeout="auto",
            language="en-IN",
        )
        gather.say(
            "Please say the location now.",
            voice="Polly.Aditi",
            language="en-IN",
        )
        response.append(gather)

        # If no input, retry
        response.say("We did not receive any input. Please call again.")
        response.hangup()

        return str(response)

    # ── Step 2: Acknowledge location, ask for description ──────
    @staticmethod
    def ask_for_description(location: str) -> str:
        """Acknowledge the location and ask for accident details."""
        response = VoiceResponse()
        response.say(
            f"Thank you. We have noted the location as: {location}. "
            "Now please describe what happened at the accident. "
            "Include details like number of vehicles, injuries, "
            "and any fire or hazardous materials.",
            voice="Polly.Aditi",
            language="en-IN",
        )

        gather = Gather(
            input="speech",
            action=f"/api/v1/voice/report?location={location}",
            method="POST",
            timeout=5,
            speech_timeout="auto",
            language="en-IN",
        )
        gather.say(
            "Please describe the accident now.",
            voice="Polly.Aditi",
            language="en-IN",
        )
        response.append(gather)

        response.say("We did not receive a description. Your location has been noted.")
        response.hangup()

        return str(response)

    # ── Step 3: Confirm the report ─────────────────────────────
    @staticmethod
    def report_confirmation(
        criticality: str,
        accident_id: str,
        volunteer_dispatched: bool,
    ) -> str:
        """Generate TwiML to confirm the report was processed."""
        response = VoiceResponse()

        crit_text = "highly critical" if criticality == "Highly Critical" else "moderate"

        message = (
            f"Your accident report has been registered successfully. "
            f"The incident has been classified as {crit_text}. "
        )

        if volunteer_dispatched:
            message += (
                "A volunteer has been dispatched to your location. "
                "Please stay safe and wait for assistance."
            )
        else:
            message += (
                "Our team has been notified and help is on the way. "
                "Please stay safe."
            )

        message += (
            f" Your report reference number is: "
            f"{accident_id[:8]}. "
            "Thank you for reporting."
        )

        response.say(message, voice="Polly.Aditi", language="en-IN")
        response.hangup()

        return str(response)

    # ── Extract assistance types from speech ───────────────────
    @staticmethod
    def extract_assistance_from_speech(text: str) -> list[str]:
        """Infer assistance types from the accident description."""
        text_lower = text.lower()
        assistance = []

        patterns = {
            "ambulance": [
                "ambulance", "injured", "hurt", "bleeding", "unconscious",
                "hospital", "medical", "fracture", "broken",
            ],
            "fire_truck": [
                "fire", "burning", "flames", "smoke", "explosion",
                "exploded", "fuel leak",
            ],
            "police": [
                "police", "hit and run", "fled", "drunk", "stolen",
                "road block", "traffic",
            ],
            "rescue": [
                "trapped", "stuck", "pinned", "collapsed", "overturned",
                "rolled over", "submerged", "drowning",
            ],
            "hazmat": [
                "chemical", "toxic", "hazardous", "gas leak", "spill",
                "contamination",
            ],
        }

        for service, keywords in patterns.items():
            if any(kw in text_lower for kw in keywords):
                assistance.append(service)

        # Default: at least traffic police for any reported accident
        if not assistance:
            assistance = ["police"]

        return assistance
