"""
Pitch velocity and arsenal calculations for scouting reports.
"""
import json
import random


PITCH_VELOCITY_BASE = {
    "4SFB": 94.0,
    "2SFB": 93.0,
    "CUT": 89.0,
    "SI": 93.0,
    "SL": 85.0,
    "CB": 79.0,
    "CH": 85.0,
    "SPL": 86.0,
    "KC": 78.0,
    "SW": 82.0,
    "SC": 80.0,
    "KN": 78.0,
}

PITCH_LABELS = {
    "4SFB": "4-Seam FB",
    "2SFB": "2-Seam FB",
    "CUT": "Cutter",
    "SI": "Sinker",
    "SL": "Slider",
    "CB": "Curveball",
    "CH": "Changeup",
    "SPL": "Splitter",
    "KC": "Knuckle Curve",
    "SW": "Sweeper",
    "SC": "Screwball",
    "KN": "Knuckleball",
}


def calculate_pitch_arsenal(pitcher, uncertainty, scout_quality):
    """
    Calculate velocity and rating data for pitcher's arsenal.

    Args:
        pitcher: Player row dict with stuff_rating and pitch_repertoire_json
        uncertainty: Scout uncertainty margin
        scout_quality: Scout quality rating (0-100)

    Returns:
        List of pitch dicts with type, label, avg_velocity, top_velocity, rating
    """
    # Get pitcher's repertoire
    repertoire = []
    if pitcher.get("pitch_repertoire_json"):
        try:
            repertoire = json.loads(pitcher["pitch_repertoire_json"])
        except (json.JSONDecodeError, TypeError):
            repertoire = []

    # Fallback to default arsenal if empty
    if not repertoire:
        position = pitcher.get("position", "SP")
        if position == "SP":
            # Starters get 4 pitches
            repertoire = [
                {"type": "4SFB", "rating": pitcher.get("stuff_rating", 50), "usage": 0.35},
                {"type": "SL", "rating": pitcher.get("control_rating", 50), "usage": 0.25},
                {"type": "CB", "rating": pitcher.get("control_rating", 50), "usage": 0.20},
                {"type": "CH", "rating": pitcher.get("control_rating", 50), "usage": 0.20},
            ]
        else:
            # Relievers get 2-3 pitches
            repertoire = [
                {"type": "4SFB", "rating": pitcher.get("stuff_rating", 50), "usage": 0.60},
                {"type": "SL", "rating": pitcher.get("control_rating", 50), "usage": 0.40},
            ]

    result = []
    stuff_rating = pitcher.get("stuff_rating", 50)

    for pitch_data in repertoire:
        pitch_type = pitch_data.get("type", "4SFB")
        base_velo = PITCH_VELOCITY_BASE.get(pitch_type, 90.0)
        rating = pitch_data.get("rating", 50)

        # Adjust velocity based on stuff_rating
        # Formula: base_velo + (stuff_rating - 50) * 0.15
        velo_adj = (stuff_rating - 50) * 0.15
        avg_velo = base_velo + velo_adj

        # Add scout uncertainty (noise)
        scout_noise = random.uniform(-2, 2) if scout_quality < 70 else random.uniform(-1, 1)
        avg_velo += scout_noise

        # Top velocity is 2-4 mph higher
        top_velo = avg_velo + random.uniform(2, 4)

        result.append({
            "type": pitch_type,
            "label": PITCH_LABELS.get(pitch_type, pitch_type),
            "avg_velocity": round(avg_velo, 1),
            "top_velocity": round(top_velo, 1),
            "rating": min(80, max(20, rating)),
        })

    return result
