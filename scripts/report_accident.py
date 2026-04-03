#!/usr/bin/env python3
"""
SmartAccident — Accident Reporter Script

Simulates a user reporting an accident via the Trello API,
then triggers the backend webhook pipeline to process it.

This is the EXACT flow that happens in production:
  1. User calls Trello API → creates a card (accident report)
  2. Script builds the webhook payload (same format Trello sends)
  3. Script POSTs to the backend webhook endpoint
  4. Backend processes: parse → geocode → ML predict → store → dispatch

Usage:
    python scripts/report_accident.py

You can also pass arguments:
    python scripts/report_accident.py \\
        --location "Civil Lines, Nagpur" \\
        --description "Multi-vehicle collision, 5 injured" \\
        --severity red \\
        --assistance ambulance fire_truck
"""

import argparse
import json
import sys
import os

# Add backend to path for settings
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

try:
    import httpx
except ImportError:
    print("❌ httpx not installed. Run: pip install httpx")
    sys.exit(1)


# ── Config ─────────────────────────────────────────────────────
TRELLO_API_BASE = "https://api.trello.com/1"
BACKEND_WEBHOOK_URL = "http://localhost:8000/api/v1/webhooks/trello"

# Load from .env or environment
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    env[key.strip()] = value.strip()
    return env

env = load_env()
TRELLO_API_KEY = env.get("TRELLO_API_KEY", os.getenv("TRELLO_API_KEY", ""))
TRELLO_API_TOKEN = env.get("TRELLO_API_TOKEN", os.getenv("TRELLO_API_TOKEN", ""))
TRELLO_BOARD_ID = env.get("TRELLO_BOARD_ID", "69cff2fd62350b3e0aba78e7")


# ── Predefined accident scenarios for quick testing ────────────
SCENARIOS = {
    "critical": {
        "location": "NH44 Toll Plaza, Nagpur",
        "description": (
            "Major accident: Bus overturned after collision with fuel tanker. "
            "15 passengers injured, 4 trapped in wreckage. "
            "Fuel leaking, fire risk imminent. Road completely blocked."
        ),
        "severity": "red",
        "assistance": ["ambulance", "fire_truck", "rescue", "police"],
    },
    "moderate": {
        "location": "MG Road, Bangalore",
        "description": (
            "Minor fender bender between two cars at traffic signal. "
            "Small dent on rear bumper. Both drivers are okay and "
            "exchanging insurance details. Traffic slightly slowed."
        ),
        "severity": "yellow",
        "assistance": ["traffic_police"],
    },
    "fire": {
        "location": "Eastern Express Highway, Mumbai",
        "description": (
            "Chemical tanker explosion on highway. Massive fire engulfing "
            "3 nearby vehicles. Thick toxic smoke spreading. "
            "12 people hospitalized with burns and breathing difficulties. "
            "Area evacuation in progress."
        ),
        "severity": "red",
        "assistance": ["fire_truck", "ambulance", "hazmat", "police"],
    },
    "pedestrian": {
        "location": "Station Road, Pune",
        "description": (
            "Speeding car hit 3 pedestrians near railway station crossing. "
            "One victim unconscious with head injury. "
            "Two others have leg fractures. Driver fled the scene."
        ),
        "severity": "red",
        "assistance": ["ambulance", "police"],
    },
    "minor": {
        "location": "Parking Area, Phoenix Mall",
        "description": (
            "Car reversed into a pillar in parking garage. "
            "Taillight broken and small dent on bumper. "
            "No injuries. Driver filing insurance claim."
        ),
        "severity": "green",
        "assistance": [],
    },
}


def get_color_emoji(color: str) -> str:
    return {"red": "🔴", "orange": "🟠", "yellow": "🟡", "green": "🟢"}.get(color, "⚪")


def step1_create_trello_card(location: str, description: str, severity: str, assistance: list[str]) -> dict | None:
    """Step 1: Create a card on Trello (simulates user reporting)."""
    print("\n" + "=" * 60)
    print("📋 STEP 1: Creating Trello Card (User Reporting Accident)")
    print("=" * 60)

    # Find first list on the board
    with httpx.Client() as client:
        lists_resp = client.get(
            f"{TRELLO_API_BASE}/boards/{TRELLO_BOARD_ID}/lists",
            params={"key": TRELLO_API_KEY, "token": TRELLO_API_TOKEN, "fields": "name,id"},
            timeout=10,
        )
        lists_resp.raise_for_status()
        lists = lists_resp.json()
        target_list = lists[0]["id"]  # First list (e.g. "To Do")

        print(f"   Board: {TRELLO_BOARD_ID}")
        print(f"   List:  {lists[0]['name']} ({target_list})")

        # Create the card
        card_data = {
            "key": TRELLO_API_KEY,
            "token": TRELLO_API_TOKEN,
            "idList": target_list,
            "name": location,
            "desc": description,
        }
        card_resp = client.post(f"{TRELLO_API_BASE}/cards", data=card_data, timeout=10)
        card_resp.raise_for_status()
        card = card_resp.json()

        print(f"\n   ✅ Card created!")
        print(f"   Card ID:  {card['id']}")
        print(f"   Name:     {card['name']}")
        print(f"   URL:      {card['shortUrl']}")
        print(f"   Desc:     {description[:80]}...")

        # Add labels if severity specified
        if severity:
            # Get or create label
            labels_resp = client.get(
                f"{TRELLO_API_BASE}/boards/{TRELLO_BOARD_ID}/labels",
                params={"key": TRELLO_API_KEY, "token": TRELLO_API_TOKEN},
                timeout=10,
            )
            labels = labels_resp.json()

            # Find label matching severity color
            target_label = None
            for label in labels:
                if label.get("color") == severity:
                    target_label = label
                    break

            if target_label:
                client.post(
                    f"{TRELLO_API_BASE}/cards/{card['id']}/idLabels",
                    data={"key": TRELLO_API_KEY, "token": TRELLO_API_TOKEN, "value": target_label["id"]},
                    timeout=10,
                )
                print(f"   Label:    {get_color_emoji(severity)} {severity} (severity)")

        return card


def step2_trigger_webhook(card: dict, severity: str, assistance: list[str]):
    """Step 2: Trigger the backend webhook (simulates what Trello would POST)."""
    print("\n" + "=" * 60)
    print("🔔 STEP 2: Triggering Backend Webhook")
    print("=" * 60)

    # Build the exact payload Trello sends
    labels = []
    if severity:
        labels.append({"color": severity, "name": ""})
    for a in (assistance or []):
        labels.append({"color": "blue", "name": a})

    payload = {
        "action": {
            "type": "createCard",
            "data": {
                "card": {
                    "id": card["id"],
                    "name": card["name"],
                    "desc": card.get("desc", ""),
                    "labels": labels,
                }
            }
        }
    }

    print(f"   Endpoint: {BACKEND_WEBHOOK_URL}")
    print(f"   Card ID:  {card['id']}")
    print(f"   Payload size: {len(json.dumps(payload))} bytes")

    with httpx.Client() as client:
        resp = client.post(BACKEND_WEBHOOK_URL, json=payload, timeout=30)

    if resp.status_code != 200:
        print(f"\n   ❌ Backend returned {resp.status_code}")
        print(f"   Response: {resp.text}")
        return

    result = resp.json()
    print(f"\n   ✅ Backend processed successfully!")
    return result


def step3_display_results(result: dict):
    """Step 3: Display the processing results."""
    print("\n" + "=" * 60)
    print("📊 STEP 3: Processing Results")
    print("=" * 60)

    criticality = result.get("criticality", "Unknown")
    crit_emoji = "🔴" if criticality == "Highly Critical" else "🟡"

    print(f"\n   Accident ID:   {result.get('accident_id')}")
    print(f"   Location:      {result.get('location_name')}")
    print(f"   Criticality:   {crit_emoji} {criticality}")

    ml = result.get("ml_prediction", {})
    if ml:
        print(f"   ML Method:     {ml.get('method', 'N/A')}")
        conf = ml.get("confidence", 0)
        print(f"   ML Confidence: {conf*100:.1f}%")

    print(f"   Geocoded:      {'✅' if result.get('geocoded') else '⚠️  No (API key needed)'}")

    dispatch = result.get("dispatch")
    if dispatch:
        print(f"\n   🚨 VOLUNTEER DISPATCHED!")
        print(f"   Task ID:       {dispatch.get('task_id')}")
        print(f"   Volunteer ID:  {dispatch.get('volunteer_id')}")
        print(f"   Status:        {dispatch.get('status')}")
    else:
        print(f"\n   ⏳ No volunteers available nearby — awaiting dispatch")

    print("\n" + "=" * 60)
    print("✅ END-TO-END TEST COMPLETE")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Report an accident via Trello API")
    parser.add_argument("--scenario", choices=SCENARIOS.keys(),
                        help="Use a predefined scenario")
    parser.add_argument("--location", help="Accident location name")
    parser.add_argument("--description", help="Accident description")
    parser.add_argument("--severity", choices=["red", "orange", "yellow", "green"],
                        default="", help="Severity color label")
    parser.add_argument("--assistance", nargs="*", default=[],
                        help="Assistance types (e.g. ambulance fire_truck)")
    parser.add_argument("--list-scenarios", action="store_true",
                        help="List available scenarios")
    args = parser.parse_args()

    if args.list_scenarios:
        print("\n📋 Available test scenarios:\n")
        for name, s in SCENARIOS.items():
            crit = "🔴" if s["severity"] == "red" else "🟡" if s["severity"] == "yellow" else "🟢"
            print(f"  {crit} {name:12s} — {s['location']}")
            print(f"     {s['description'][:80]}...")
            print()
        return

    # Pick scenario or use CLI args
    if args.scenario:
        s = SCENARIOS[args.scenario]
        location = s["location"]
        description = s["description"]
        severity = s["severity"]
        assistance = s["assistance"]
    elif args.location and args.description:
        location = args.location
        description = args.description
        severity = args.severity
        assistance = args.assistance or []
    else:
        # Interactive mode — pick a scenario
        print("\n🚨 SmartAccident — Accident Reporter")
        print("=" * 40)
        print("\nPick a test scenario:\n")
        scenario_list = list(SCENARIOS.items())
        for i, (name, s) in enumerate(scenario_list, 1):
            crit = "🔴" if s["severity"] == "red" else "🟡" if s["severity"] == "yellow" else "🟢"
            print(f"  {i}. {crit} {name:12s} — {s['location']}")

        try:
            choice = int(input("\nEnter number (1-5): ")) - 1
            name, s = scenario_list[choice]
        except (ValueError, IndexError):
            name, s = scenario_list[0]  # Default to critical
            print(f"  → Using default: {name}")

        location = s["location"]
        description = s["description"]
        severity = s["severity"]
        assistance = s["assistance"]

    # Validate credentials
    if not TRELLO_API_KEY or not TRELLO_API_TOKEN:
        print("❌ Trello API credentials not found!")
        print("   Set TRELLO_API_KEY and TRELLO_API_TOKEN in .env")
        sys.exit(1)

    print(f"\n🚨 Reporting accident at: {location}")
    print(f"   Severity: {get_color_emoji(severity)} {severity or 'none'}")
    print(f"   Assistance: {', '.join(assistance) if assistance else 'none'}")

    # Run the full pipeline
    try:
        card = step1_create_trello_card(location, description, severity, assistance)
        if card is None:
            print("❌ Failed to create Trello card")
            sys.exit(1)

        result = step2_trigger_webhook(card, severity, assistance)
        if result:
            step3_display_results(result)
    except httpx.ConnectError:
        print("\n❌ Cannot connect to backend at", BACKEND_WEBHOOK_URL)
        print("   Make sure the server is running:")
        print("   cd backend && uvicorn src.main:app --reload")
        sys.exit(1)
    except httpx.HTTPError as e:
        print(f"\n❌ HTTP error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
