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
    "hit_and_run_freq": "normal",    # conservative, normal, aggressive
    "squeeze_freq": "conservative",  # conservative, normal, aggressive
    "shift_tendency": 0.7,           # 0-1, how often to deploy shift
    "defensive_sub_tendency": 0.6,   # 0-1, how often to make late-game defensive subs
    "aggression": 50,                # 0-100, overall team aggression/strategy
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

HIT_AND_RUN_MULTIPLIER = {
    "conservative": 0.3,
    "normal": 1.0,
    "aggressive": 2.0,
}

SQUEEZE_MULTIPLIER = {
    "conservative": 0.2,
    "normal": 0.8,
    "aggressive": 1.5,
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
