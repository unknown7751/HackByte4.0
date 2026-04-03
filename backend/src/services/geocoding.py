"""
Google Maps Geocoding service.

Converts human-readable location names (e.g. "Civil Lines, Nagpur")
into latitude/longitude coordinates using the Google Maps Geocoding API.
Falls back gracefully when the API key is not configured.
"""

import logging

import httpx

from src.config.settings import settings
from src.schemas.accident import LatLng

logger = logging.getLogger(__name__)

GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"


class GeocodingService:
    """Geocodes location names to lat/lng via Google Maps API."""

    def __init__(self):
        self.api_key = settings.GOOGLE_MAPS_API_KEY

    @property
    def is_configured(self) -> bool:
        """Check if the API key is set (not placeholder)."""
        return bool(self.api_key) and self.api_key not in ("", "your_key")

    async def geocode(self, address: str) -> LatLng | None:
        """Convert an address string to a LatLng.

        Returns None if:
          - API key is not configured
          - Geocoding fails
          - No results found
        """
        if not self.is_configured:
            logger.warning(
                "Google Maps API key not configured — skipping geocoding for '%s'",
                address,
            )
            return None

        params = {
            "address": address,
            "key": self.api_key,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(GEOCODING_URL, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != "OK" or not data.get("results"):
                logger.warning(
                    "Geocoding returned no results for '%s': status=%s",
                    address,
                    data.get("status"),
                )
                return None

            location = data["results"][0]["geometry"]["location"]
            result = LatLng(lat=location["lat"], lng=location["lng"])
            logger.info("Geocoded '%s' → (%s, %s)", address, result.lat, result.lng)
            return result

        except httpx.HTTPError as e:
            logger.error("Geocoding request failed for '%s': %s", address, e)
            return None
        except (KeyError, IndexError) as e:
            logger.error("Unexpected geocoding response structure: %s", e)
            return None
