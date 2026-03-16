"""
Front Office - Team Strategy Settings
Configurable tactical preferences that influence game simulation.
"""

DEFAULT_STRATEGY = {
    "steal_frequency": "normal",      # conservative, normal, aggressive
    "bunt_frequency": "normal",       # never, sacrifice_only, normal, aggressive
    "pitch_count_limit": 100,         # starter max pitches
    "ibb_threshold": 80,             # power rating threshold for IBB consideration
    "infield_in_threshold": 7,       # inning to start considering infield in
}

STEAL_FREQUENCY_MULTIPLIER = {
    "conservative": 0.5,
    "normal": 1.0,
    "aggressive": 2.0,
}

BUNT_FREQUENCY_CONFIG = {
    "never": 0.0,
    "sacrifice_only": 0.03,   # ~3% of eligible PAs
    "normal": 0.05,
    "aggressive": 0.10,
}


def get_strategy(strategy_json: str = None) -> dict:
    """Parse team strategy JSON, falling back to defaults."""
    import json
    strategy = dict(DEFAULT_STRATEGY)
    if strategy_json:
        try:
            overrides = json.loads(strategy_json)
            strategy.update(overrides)
        except (json.JSONDecodeError, TypeError):
            pass
    return strategy
