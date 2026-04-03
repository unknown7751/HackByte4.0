"""
Trello integration service.

Handles:
- Parsing incoming Trello webhook payloads (card creation/update)
- Extracting accident details from card fields
- Registering webhooks with the Trello API
"""

import logging
from dataclasses import dataclass

import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)

TRELLO_API_BASE = "https://api.trello.com/1"


@dataclass
class ParsedAccidentReport:
    """Structured data extracted from a Trello card."""
    trello_card_id: str
    description: str | None
    location_name: str
    criticality_hint: str | None       # from labels
    assistance_required: list[str]      # from checklist / labels


class TrelloService:
    """Service for interacting with Trello API and parsing webhook payloads."""

    def __init__(self):
        self.api_key = settings.TRELLO_API_KEY
        self.api_token = settings.TRELLO_API_TOKEN

    @property
    def _auth_params(self) -> dict:
        return {"key": self.api_key, "token": self.api_token}

    # ── Webhook payload parsing ────────────────────────────────
    def parse_webhook_payload(self, payload: dict) -> ParsedAccidentReport | None:
        """Parse a Trello webhook payload and extract accident data.

        Expected Trello card format:
          - Card name  → location_name (e.g. "Civil Lines, Nagpur")
          - Card desc  → description of the accident
          - Labels     → criticality hints and assistance types
                         Red/Orange label → "Highly Critical"
                         Yellow/Green     → "Moderate"
                         Other labels     → assistance types (e.g. "ambulance", "fire_truck")
          - Checklist  → assistance_required items

        Returns None if the payload is not a card creation event.
        """
        action = payload.get("action", {})
        action_type = action.get("type")

        # We care about card creation and updates
        if action_type not in ("createCard", "updateCard"):
            logger.debug("Ignoring Trello action type: %s", action_type)
            return None

        card = action.get("data", {}).get("card", {})
        card_id = card.get("id")
        if not card_id:
            logger.warning("Trello payload missing card ID")
            return None

        # Extract basic fields
        card_name = card.get("name", "").strip()
        card_desc = card.get("desc", "").strip() or None

        if not card_name:
            logger.warning("Trello card %s has no name, skipping", card_id)
            return None

        # Parse labels for criticality and assistance
        labels = card.get("labels", [])
        criticality_hint = None
        assistance_types = []

        for label in labels:
            color = (label.get("color") or "").lower()
            name = (label.get("name") or "").strip().lower()

            # Red/orange labels → Highly Critical
            if color in ("red", "orange"):
                criticality_hint = "Highly Critical"
            elif color in ("yellow", "green") and criticality_hint is None:
                criticality_hint = "Moderate"

            # Named labels → assistance types
            if name and name not in ("moderate", "highly critical", "critical"):
                assistance_types.append(name)

        return ParsedAccidentReport(
            trello_card_id=card_id,
            description=card_desc,
            location_name=card_name,
            criticality_hint=criticality_hint,
            assistance_required=assistance_types if assistance_types else None,
        )

    # ── Fetch full card details ────────────────────────────────
    async def fetch_card_details(self, card_id: str) -> dict | None:
        """Fetch complete card data from Trello API (labels, checklists, etc.)."""
        url = f"{TRELLO_API_BASE}/cards/{card_id}"
        params = {
            **self._auth_params,
            "fields": "name,desc,labels",
            "checklists": "all",
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, timeout=10)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as e:
            logger.error("Failed to fetch Trello card %s: %s", card_id, e)
            return None

    # ── Parse assistance from checklists ───────────────────────
    @staticmethod
    def extract_checklist_items(card_data: dict) -> list[str]:
        """Extract checked items from Trello checklists as assistance types."""
        items = []
        for checklist in card_data.get("checklists", []):
            for item in checklist.get("checkItems", []):
                if item.get("state") == "complete":
                    items.append(item.get("name", "").strip().lower())
        return [i for i in items if i]

    # ── Register webhook ───────────────────────────────────────
    async def register_webhook(self, callback_url: str, board_id: str) -> dict | None:
        """Register a webhook with Trello for a specific board.

        Args:
            callback_url: Public URL that Trello will POST to (e.g. https://yourdomain.com/api/v1/webhooks/trello)
            board_id: Trello board ID to watch

        Returns:
            Webhook registration response or None on failure
        """
        url = f"{TRELLO_API_BASE}/webhooks"
        data = {
            **self._auth_params,
            "callbackURL": callback_url,
            "idModel": board_id,
            "description": "SmartAccident webhook",
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=data, timeout=10)
                resp.raise_for_status()
                result = resp.json()
                logger.info("Trello webhook registered: %s", result.get("id"))
                return result
        except httpx.HTTPError as e:
            logger.error("Failed to register Trello webhook: %s", e)
            return None

    # ── List existing webhooks ─────────────────────────────────
    async def list_webhooks(self) -> list[dict]:
        """List all active webhooks for the current token."""
        url = f"{TRELLO_API_BASE}/tokens/{self.api_token}/webhooks"
        params = self._auth_params
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, timeout=10)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as e:
            logger.error("Failed to list webhooks: %s", e)
            return []
