"""
Front Office - Rating Scale Conversions
Converts between the internal 20-80 scout scale and display scales.

Supported scales:
- "20-80"   : Scout scale (internal, default)
- "50-100"  : Baseball Mogul default
- "1-20"    : Football Manager style
- "1-100"   : Percentage
- "letter"  : Letter grades (A+ through F)
"""

# Letter grade thresholds (mapped from 20-80 scale)
LETTER_GRADES = [
    (80, "A+"), (75, "A"), (70, "A-"),
    (65, "B+"), (60, "B"), (55, "B-"),
    (50, "C+"), (45, "C"), (40, "C-"),
    (35, "D+"), (30, "D"), (25, "D-"),
    (20, "F"),
]

VALID_SCALES = {"20-80", "50-100", "1-20", "1-100", "letter"}


def convert_rating(value: int, scale: str):
    """
    Convert a 20-80 internal rating to the specified display scale.

    Args:
        value: Rating on 20-80 scale
        scale: Target scale name

    Returns:
        Converted value (int for numeric scales, str for letter)
    """
    # Clamp to valid range
    value = max(20, min(80, value))

    if scale == "20-80":
        return value

    # Normalize to 0-1 range (20 = 0.0, 80 = 1.0)
    normalized = (value - 20) / 60.0

    if scale == "50-100":
        return round(50 + normalized * 50)

    if scale == "1-20":
        return max(1, round(1 + normalized * 19))

    if scale == "1-100":
        return max(1, round(1 + normalized * 99))

    if scale == "letter":
        for threshold, grade in LETTER_GRADES:
            if value >= threshold:
                return grade
        return "F"

    # Fallback to raw value
    return value


def get_scale_info(scale: str) -> dict:
    """Get display information for a scale."""
    info = {
        "20-80": {
            "name": "Scout (20-80)",
            "description": "Traditional scouting scale used by MLB scouts",
            "min": 20, "max": 80, "type": "numeric",
        },
        "50-100": {
            "name": "Baseball Mogul (50-100)",
            "description": "Baseball Mogul default rating scale",
            "min": 50, "max": 100, "type": "numeric",
        },
        "1-20": {
            "name": "Football Manager (1-20)",
            "description": "Football Manager style 1-20 scale",
            "min": 1, "max": 20, "type": "numeric",
        },
        "1-100": {
            "name": "Percentage (1-100)",
            "description": "Standard percentage scale",
            "min": 1, "max": 100, "type": "numeric",
        },
        "letter": {
            "name": "Letter Grade (A+ - F)",
            "description": "Academic-style letter grades",
            "min": "F", "max": "A+", "type": "letter",
        },
    }
    return info.get(scale, info["20-80"])


def get_color_thresholds(scale: str) -> dict:
    """
    Return color-class thresholds for a given scale.
    Returns {elite, good, avg} thresholds (values >= threshold get that class).
    """
    if scale == "20-80":
        return {"elite": 65, "good": 50, "avg": 35}
    elif scale == "50-100":
        return {"elite": 87, "good": 75, "avg": 62}
    elif scale == "1-20":
        return {"elite": 15, "good": 10, "avg": 5}
    elif scale == "1-100":
        return {"elite": 75, "good": 50, "avg": 25}
    elif scale == "letter":
        # For letter grades, use the 20-80 thresholds internally
        return {"elite": 65, "good": 50, "avg": 35}
    return {"elite": 65, "good": 50, "avg": 35}
