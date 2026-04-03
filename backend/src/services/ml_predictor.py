"""
Accident criticality prediction service.

Uses a trained TF-IDF + Gradient Boosting model to classify accidents
as "Moderate" or "Highly Critical" based on description text.

Falls back to a rule-based keyword engine if the trained model is not
available (e.g. first run before training).

Model is trained via: python ml-model/train.py
"""

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Attempt to load the trained model ──────────────────────────
_MODEL = None
_MODEL_LOAD_ATTEMPTED = False


def _load_model():
    """Lazy-load the trained sklearn pipeline from disk."""
    global _MODEL, _MODEL_LOAD_ATTEMPTED
    if _MODEL_LOAD_ATTEMPTED:
        return _MODEL
    _MODEL_LOAD_ATTEMPTED = True

    # Search for model in likely locations
    possible_paths = [
        Path(__file__).resolve().parents[3] / "ml-model" / "model.joblib",   # backend/src/services -> project root
        Path(__file__).resolve().parents[2] / "ml-model" / "model.joblib",   # fallback
        Path.cwd() / "ml-model" / "model.joblib",                           # cwd-based
        Path.cwd().parent / "ml-model" / "model.joblib",                     # from backend/
    ]

    for path in possible_paths:
        if path.exists():
            try:
                import joblib
                _MODEL = joblib.load(path)
                logger.info("Loaded trained ML model from: %s", path)
                return _MODEL
            except Exception as e:
                logger.error("Failed to load model from %s: %s", path, e)
                return None

    logger.warning(
        "No trained model found. Using rule-based fallback. "
        "Train with: python ml-model/train.py"
    )
    return None


# ── Rule-based fallback keywords ───────────────────────────────
HIGH_CRIT_KEYWORDS = {
    "fatal", "death", "died", "dead", "killed",
    "trapped", "unconscious", "unresponsive", "critical",
    "severe", "major", "massive",
    "pile-up", "pileup", "multi-vehicle", "multiple vehicles",
    "bus", "truck", "tanker", "overturned", "rollover",
    "fire", "flames", "burning", "explosion", "exploded",
    "fuel", "gas leak", "hazardous", "chemical", "toxic",
    "bridge", "collapsed", "collapse",
    "children", "pedestrian", "cyclist", "many injured",
    "mass casualty",
}

MODERATE_KEYWORDS = {
    "minor", "fender bender", "fender-bender",
    "scratch", "dent", "slow speed", "parking",
    "no injuries", "no injury",
}


class MLPredictor:
    """Predicts accident criticality: 'Moderate' or 'Highly Critical'.

    Uses a trained sklearn model when available, otherwise falls back
    to keyword-based scoring.
    """

    def __init__(self):
        self._model = _load_model()

    def predict(
        self,
        description: str | None = None,
        assistance_required: list[str] | None = None,
        location_name: str | None = None,
    ) -> str:
        """Predict criticality for an accident.

        Args:
            description: Free-text description of the accident
            assistance_required: List of assistance types requested
            location_name: Name/address of the accident location

        Returns:
            'Moderate' or 'Highly Critical'
        """
        # Combine all text into one input
        text = " ".join(filter(None, [description, location_name])).strip()

        # Add assistance types to text for model context
        if assistance_required:
            text += " " + " ".join(assistance_required)

        if not text:
            logger.warning("No text provided for prediction — defaulting to Moderate")
            return "Moderate"

        # Try trained model first
        if self._model is not None:
            return self._predict_with_model(text)

        # Fallback to rules
        return self._predict_with_rules(text, assistance_required)

    def predict_with_confidence(
        self,
        description: str | None = None,
        assistance_required: list[str] | None = None,
        location_name: str | None = None,
    ) -> dict:
        """Predict criticality with confidence score.

        Returns:
            {
                "prediction": "Moderate" or "Highly Critical",
                "confidence": float (0-1),
                "method": "ml_model" or "rule_based"
            }
        """
        text = " ".join(filter(None, [description, location_name])).strip()
        if assistance_required:
            text += " " + " ".join(assistance_required)

        if not text:
            return {
                "prediction": "Moderate",
                "confidence": 0.5,
                "method": "default",
            }

        if self._model is not None:
            pred = self._model.predict([text])[0]
            proba = self._model.predict_proba([text])[0]
            confidence = float(max(proba))
            return {
                "prediction": pred,
                "confidence": round(confidence, 4),
                "method": "ml_model",
            }

        pred = self._predict_with_rules(text, assistance_required)
        return {
            "prediction": pred,
            "confidence": 0.7,   # rules don't give real confidence
            "method": "rule_based",
        }

    # ── ML model prediction ────────────────────────────────────
    def _predict_with_model(self, text: str) -> str:
        """Predict using the trained sklearn pipeline."""
        try:
            prediction = self._model.predict([text])[0]
            proba = self._model.predict_proba([text])[0]
            confidence = max(proba)
            logger.info(
                "ML prediction: '%s' (%.1f%% confidence) — text: '%s'",
                prediction, confidence * 100, text[:80],
            )
            return prediction
        except Exception as e:
            logger.error("ML model prediction failed: %s — falling back to rules", e)
            return self._predict_with_rules(text, None)

    # ── Rule-based fallback ────────────────────────────────────
    def _predict_with_rules(
        self,
        text: str,
        assistance_required: list[str] | None,
    ) -> str:
        """Fallback keyword-based prediction."""
        score = 0
        text_lower = text.lower()

        for keyword in HIGH_CRIT_KEYWORDS:
            if keyword in text_lower:
                score += 2

        for keyword in MODERATE_KEYWORDS:
            if keyword in text_lower:
                score -= 2

        # Injured count heuristic
        injured_matches = re.findall(
            r"(\d+)\s*(?:injured|hurt|casualties|victims|dead|killed)", text_lower
        )
        if injured_matches:
            max_count = max(int(n) for n in injured_matches)
            if max_count >= 5:
                score += 4
            elif max_count >= 2:
                score += 2

        criticality = "Highly Critical" if score >= 2 else "Moderate"
        logger.info(
            "Rule-based prediction: score=%d → '%s' (text: '%s')",
            score, criticality, text_lower[:80],
        )
        return criticality
