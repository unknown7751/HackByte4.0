"""
Training script for the accident criticality prediction model.

Generates a synthetic dataset of accident descriptions, trains a
TF-IDF + Gradient Boosting pipeline, evaluates it, and saves
the model to ml-model/model.joblib.

Usage:
    cd backend
    python -m ml_model.train

Or from project root:
    python backend/ml_model/train.py
"""

import os
import sys
import random
import json

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix
import joblib


# ── Synthetic Data Generation ──────────────────────────────────

# Templates for generating realistic accident descriptions
HIGHLY_CRITICAL_TEMPLATES = [
    "Multi-vehicle collision on {road}. {n_injured} people injured, {n_trapped} trapped in wreckage. {extra_severe}",
    "Major accident on {road}. Bus overturned carrying {n_passengers} passengers. Multiple casualties reported.",
    "Head-on collision between truck and car on {road}. {n_injured} critically injured. Fuel leaking from tanker.",
    "Fatal accident on {road}. Vehicle caught fire after collision. {n_injured} dead, {n_trapped} people trapped.",
    "Massive pile-up involving {n_vehicles} vehicles on {road}. Visibility was poor. Emergency services needed urgently.",
    "Truck overturned on {road} spilling hazardous chemicals. Area evacuation in progress. {n_injured} people affected.",
    "High-speed collision on {road}. Car crushed under truck. {n_injured} people severely injured, immediate rescue needed.",
    "Explosion at accident site on {road} after fuel tanker collision. Fire spreading rapidly. {n_injured} casualties.",
    "Bridge collapse on {road} due to heavy vehicle overload. Multiple vehicles fallen. {n_injured} people trapped below.",
    "School bus accident on {road}. Children trapped inside overturned bus. {n_injured} injuries, parents rushing to scene.",
    "Pedestrians hit by speeding truck on {road}. {n_injured} people critically injured including children. Blood on road.",
    "Gas tanker explosion on {road}. Massive fire engulfing nearby vehicles. {n_injured} feared dead. Evacuation underway.",
    "Multi-car collision in tunnel on {road}. Fire and smoke filling tunnel. {n_injured} people unconscious from smoke.",
    "Construction crane collapsed on {road} crushing {n_vehicles} vehicles. {n_injured} workers and drivers trapped.",
    "High-speed bike crash into crowd on {road}. {n_injured} bystanders injured. Rider critically hurt and unconscious.",
    "Derailed train blocking {road}. {n_injured} passengers injured. Multiple carriages overturned. Rescue ops started.",
    "Major landslide on {road} burying {n_vehicles} vehicles. {n_injured} people missing. Heavy rescue equipment needed.",
    "Drunk driver crashed into bus stop on {road}. {n_injured} people killed. Several more in critical condition.",
    "Two buses collided head-on at {road}. {n_passengers} passengers on board. Massive casualties, ambulances needed.",
    "Oil tanker fire on {road}. Thick black smoke visible for miles. {n_injured} firefighters also injured in rescue.",
    "Severe accident on {road}. Vehicle rolled over multiple times. Passengers ejected. {n_injured} in critical state.",
    "Stampede triggered by accident on {road}. {n_injured} people trampled. Chaos at scene, crowd control needed.",
    "Car plunged off {road} into river below. {n_injured} occupants. Divers needed for underwater rescue operation.",
    "Cement mixer overturned on {road} landing on a car. {n_injured} people crushed. Heavy crane needed to lift.",
    "Electrical pole fell on vehicles on {road} after accident. Live wires on ground. {n_injured} electrocuted.",
    "Major chemical spill from truck on {road}. Toxic fumes spreading. {n_injured} people experiencing breathing difficulties.",
    "Highway pileup of {n_vehicles} cars on {road} due to fog. {n_injured} people injured across multiple vehicles.",
    "Ambulance carrying patients crashed on {road}. {n_injured} people now critical. Both original and new patients affected.",
    "Building debris fell on {road} after accident impact. {n_vehicles} vehicles buried. {n_injured} trapped in rubble.",
    "Hit and run on {road}. Victim dragged {n_vehicles}00 meters. Critical injuries, massive internal bleeding.",
]

MODERATE_TEMPLATES = [
    "Minor fender bender on {road}. Two cars involved. No injuries reported. Traffic slightly affected.",
    "Small accident on {road}. Rear-end collision at traffic signal. Minor damage to bumpers. Drivers exchanging details.",
    "Bike skidded on {road} due to oil spill. Rider has minor scratches. No other vehicles involved.",
    "Parking lot accident at {location}. Car reversed into another vehicle. Paint scratches only. No injuries.",
    "Minor collision at {road} intersection. Both drivers alert and talking. Small dent on fender. Traffic moving.",
    "Auto-rickshaw and car minor scrape on {road}. Slight mirror damage. Both drivers arguing but uninjured.",
    "Two-wheeler slipped on wet {road}. Rider wearing helmet, has minor bruises. Bike has cosmetic damage.",
    "Side mirror clipped on narrow {road}. Minor glass breakage. No injuries. Both parties cooperating.",
    "Vehicle hit a stray dog on {road}. Minor bumper damage. Animal ran away. Driver stopped to check.",
    "Low-speed collision in traffic jam on {road}. Bumper to bumper touch. No injuries, minimal damage.",
    "Car door opened into passing cyclist on {road}. Cyclist has minor elbow scratch. No serious injury.",
    "Tree branch fell on parked car at {road}. Windshield cracked. No one inside. Owner filing insurance.",
    "Pothole caused tire burst on {road}. Vehicle pulled over safely. No collision. Waiting for replacement.",
    "Taxi and auto minor touch at {road} corner. Both vehicles operational. Passengers unhurt. Horn argument ongoing.",
    "Slow-speed rear-end hit at {road} toll plaza. Minor scratch. No injury. Both drivers exchanging information.",
    "Vehicle rolled backward slightly on {road} slope. Tapped car behind. Tiny dent. No injuries at all.",
    "Minor sideswipe between two cars on {road}. Paint transfer only. Both drivers walking and fine.",
    "Cyclist fell after hitting pothole on {road}. Minor knee scrape. Cyclist walked away pushing bike.",
    "Car stalled and was lightly bumped from behind on {road}. No injuries. Mechanic called for tow.",
    "Water tanker brushed against parked car on {road}. Side panel scratch. No occupants in parked car.",
    "Electric scooter tipped over on {road}. Rider unhurt but scooter has broken footrest. No collision.",
    "Minor accident at parking garage at {location}. Scraped pillar while turning. No other vehicle involved.",
    "Food delivery bike slipped on {road}. Rider okay with helmet. Food spillage only. No traffic disruption.",
    "Car went over speed bump too fast on {road}. Scraping sound underneath. No collision. Car seems fine.",
    "Learner driver stalled at {road} signal. Car behind honked and lightly tapped. Zero damage. Learning moment.",
    "Branch scratch on car roof on {road}. Cosmetic damage only. No personnel injury. Owner annoyed.",
    "Minor bump between school van and wall at {location}. No children on board. Driver is fine.",
    "Truck side-view mirror hit signboard on {road}. Mirror cracked. No other damage. Driver continued.",
    "Motorcycle slid on gravel on {road}. Rider has road rash on arm. Helmet saved head. Rider walking.",
    "Bus grazed a bollard on {road}. Minor paint scrape. All passengers safe. Bus continued on route.",
]

ROADS = [
    "NH44", "NH48", "NH7", "Mumbai-Pune Expressway", "Eastern Express Highway",
    "Ring Road", "Outer Ring Road", "Nagpur-Hyderabad Highway", "GT Road",
    "Yamuna Expressway", "Agra-Lucknow Expressway", "Pune-Bangalore Highway",
    "Chennai-Bangalore Highway", "Kolkata-Delhi Highway", "Delhi-Jaipur Highway",
    "Ahmedabad-Vadodara Expressway", "Noida Expressway", "Western Express Highway",
    "Bandra-Worli Sea Link", "Hosur Road", "MG Road", "Station Road",
    "Airport Road", "Industrial Area Road", "Bypass Road",
]

LOCATIONS = [
    "City Mall", "Railway Station", "Bus Terminal", "Hospital Zone",
    "Metro Station", "Shopping Complex", "Market Area", "Tech Park",
    "University Campus", "Residential Colony", "Commercial District",
]

SEVERE_EXTRAS = [
    "Rescue helicopters requested.", "Army called for assistance.",
    "Road completely blocked for miles.", "ICU beds being arranged.",
    "Blood donation camps being set up nearby.",
    "Survivor reported screams from wreckage.",
    "Nearby buildings also damaged from impact.",
    "Gas masks distributed to rescue workers.",
    "National disaster response team alerted.",
    "Local hospitals overwhelmed, patients diverted.",
]


def generate_dataset(n_per_class: int = 300) -> pd.DataFrame:
    """Generate a synthetic training dataset."""
    rows = []

    for _ in range(n_per_class):
        # Highly Critical
        template = random.choice(HIGHLY_CRITICAL_TEMPLATES)
        text = template.format(
            road=random.choice(ROADS),
            location=random.choice(LOCATIONS),
            n_injured=random.randint(3, 25),
            n_trapped=random.randint(1, 10),
            n_vehicles=random.randint(3, 15),
            n_passengers=random.randint(20, 60),
            extra_severe=random.choice(SEVERE_EXTRAS),
        )
        rows.append({"description": text, "label": "Highly Critical"})

        # Moderate
        template = random.choice(MODERATE_TEMPLATES)
        text = template.format(
            road=random.choice(ROADS),
            location=random.choice(LOCATIONS),
        )
        rows.append({"description": text, "label": "Moderate"})

    random.shuffle(rows)
    return pd.DataFrame(rows)


def train_model(output_dir: str = None):
    """Train and save the criticality prediction model."""
    if output_dir is None:
        # Default: project_root/ml-model/
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "ml-model",
        )

    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("SmartAccident — ML Model Training")
    print("=" * 60)

    # Generate data
    print("\n📊 Generating synthetic training data...")
    random.seed(42)
    np.random.seed(42)
    df = generate_dataset(n_per_class=300)
    print(f"   Total samples: {len(df)}")
    print(f"   Class distribution:\n{df['label'].value_counts().to_string()}")

    # Save training data
    data_path = os.path.join(output_dir, "training_data.csv")
    df.to_csv(data_path, index=False)
    print(f"\n💾 Training data saved to: {data_path}")

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        df["description"], df["label"],
        test_size=0.2, random_state=42, stratify=df["label"],
    )
    print(f"\n📐 Train/test split: {len(X_train)} train, {len(X_test)} test")

    # Build pipeline
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 3),       # unigrams, bigrams, trigrams
            min_df=2,
            max_df=0.95,
            sublinear_tf=True,        # apply log normalization
            strip_accents="unicode",
            lowercase=True,
        )),
        ("clf", GradientBoostingClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.1,
            min_samples_split=5,
            random_state=42,
        )),
    ])

    # Cross-validation
    print("\n🔄 Running 5-fold cross-validation...")
    cv_scores = cross_val_score(pipeline, X_train, y_train, cv=5, scoring="f1_macro")
    print(f"   CV F1 scores: {cv_scores.round(4)}")
    print(f"   Mean CV F1:   {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    # Train on full training set
    print("\n🏋️ Training final model...")
    pipeline.fit(X_train, y_train)

    # Evaluate on test set
    y_pred = pipeline.predict(X_test)
    print("\n📈 Test Set Results:")
    print(classification_report(y_test, y_pred))
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    # Feature importance via TF-IDF feature names
    tfidf = pipeline.named_steps["tfidf"]
    clf = pipeline.named_steps["clf"]
    feature_names = tfidf.get_feature_names_out()
    importances = clf.feature_importances_
    top_idx = np.argsort(importances)[-20:][::-1]
    print("\n🔑 Top 20 most important features:")
    for i, idx in enumerate(top_idx, 1):
        print(f"   {i:2d}. '{feature_names[idx]}' (importance: {importances[idx]:.4f})")

    # Save model
    model_path = os.path.join(output_dir, "model.joblib")
    joblib.dump(pipeline, model_path)
    print(f"\n✅ Model saved to: {model_path}")

    # Save metadata
    metadata = {
        "model_type": "TF-IDF + GradientBoosting",
        "n_training_samples": len(X_train),
        "n_test_samples": len(X_test),
        "cv_f1_mean": round(float(cv_scores.mean()), 4),
        "cv_f1_std": round(float(cv_scores.std()), 4),
        "classes": list(pipeline.classes_),
        "tfidf_features": int(len(feature_names)),
        "ngram_range": [1, 3],
    }
    metadata_path = os.path.join(output_dir, "model_metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"📋 Metadata saved to: {metadata_path}")

    # Quick demo predictions
    print("\n🧪 Demo predictions:")
    demos = [
        "Bus overturned on highway. 15 passengers injured, 3 trapped. Fire spreading.",
        "Minor fender bender at parking lot. Small scratch on bumper. No injuries.",
        "Truck hit pedestrian on NH44. Critical head injury. Ambulance needed immediately.",
        "Two bikes collided at low speed. Both riders have minor bruises.",
        "Chemical tanker leaking on expressway. Toxic fumes. 8 people hospitalized.",
        "Car reversed into pole at mall parking. Taillight broken. Driver is fine.",
    ]
    for desc in demos:
        pred = pipeline.predict([desc])[0]
        prob = pipeline.predict_proba([desc])[0]
        confidence = max(prob) * 100
        print(f'   "{desc[:70]}..." → {pred} ({confidence:.1f}%)')

    print("\n" + "=" * 60)
    print("Training complete!")
    print("=" * 60)

    return pipeline


if __name__ == "__main__":
    train_model()
