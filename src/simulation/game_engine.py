"""
Front Office - Game Simulation Engine
Math-based game simulator producing realistic box scores from player ratings.

At-bat resolution model based on Baseball Mogul mechanics:
- Player ratings (20-80 scale) map to probability distributions
- Pitcher vs batter matchup with platoon adjustments
- Park factors modify HR/2B/3B rates
- Fatigue degrades pitcher effectiveness
- Clutch ratings affect high-leverage situations
- Count-dependent pitching with pitch types
- Error probability on batted balls
"""
import random
import math
import json
from dataclasses import dataclass, field


@dataclass
class BatterStats:
    player_id: int
    name: str
    position: str
    batting_order: int
    bats: str  # L, R, S
    contact: int
    power: int
    speed: int
    clutch: int
    fielding: int = 50
    eye: int = 50  # plate discipline: ability to draw walks & lay off pitches
    morale: int = 50  # 0-100 morale rating
    is_home: bool = False  # home field advantage flag
    platoon_split_json: str = None  # JSON with platoon splits
    height_inches: int = 73  # player height for strike zone modeling
    # Per-player strategy overrides (None = use team default)
    steal_aggression: int = 3  # 1-5 scale
    bunt_tendency: int = 3
    hit_and_run_tendency: int = 3
    # Game accumulators
    ab: int = 0
    runs: int = 0
    hits: int = 0
    doubles: int = 0
    triples: int = 0
    hr: int = 0
    rbi: int = 0
    bb: int = 0
    so: int = 0
    sb: int = 0
    cs: int = 0
    hbp: int = 0
    sf: int = 0
    errors_committed: int = 0
    reached_on_error: int = 0
    putouts: int = 0
    assists: int = 0


@dataclass
class PitcherStats:
    player_id: int
    name: str
    throws: str  # L, R
    role: str  # starter, closer, setup, middle, long
    stuff: int
    control: int
    stamina: int
    clutch: int
    pitch_order: int = 0
    # Pitch types: list of tuples [(pitch_type, effectiveness_rating)]
    pitch_types: list = field(default_factory=lambda: [("4SFB", 70), ("SL", 60), ("CB", 55)])
    # Pitch repertoire: JSON list of dicts with 'type', 'rating', 'usage'
    pitch_repertoire: list = field(default_factory=list)
    # Game accumulators
    ip_outs: int = 0
    hits_allowed: int = 0
    runs_allowed: int = 0
    er: int = 0
    bb_allowed: int = 0
    so_pitched: int = 0
    hr_allowed: int = 0
    pitches: int = 0
    is_starter: bool = False
    decision: str = None  # W, L, S, H, BS
    errors_caused: int = 0
    # Fatigue carryover from recent games (applied as temporary modifier, not saved to DB)
    fatigue_stuff_modifier: float = 1.0   # multiplier on stuff rating (e.g., 0.85 = -15%)
    fatigue_control_modifier: float = 1.0  # multiplier on control rating
    pitched_yesterday: bool = False  # flag for bullpen management decisions
    # Per-pitcher strategy override
    custom_pitch_count_limit: int = None  # None = use team setting


@dataclass
class ParkFactors:
    hr_factor: float = 1.0
    double_factor: float = 1.0
    triple_factor: float = 1.0
    hit_factor: float = 1.0
    so_factor: float = 1.0

    @classmethod
    def from_stadium(cls, lf: int, lcf: int, cf: int, rcf: int, rf: int,
                     is_dome: bool = False, altitude: int = 0,
                     surface: str = "grass", foul_territory: str = "average"):
        """Calculate park factors from stadium dimensions."""
        # Average MLB dimensions: LF=330, LCF=375, CF=400, RCF=375, RF=330
        avg_total = 330 + 375 + 400 + 375 + 330  # 1810
        actual_total = lf + lcf + cf + rcf + rf

        # Shorter fences = more HRs
        dimension_ratio = avg_total / max(actual_total, 1)
        hr_factor = 0.7 + (dimension_ratio * 0.6)  # range ~0.85-1.20

        # Altitude effect (Coors Field is ~5280 ft)
        altitude_bonus = 1.0 + (altitude / 20000)  # ~1.26 at Coors
        hr_factor *= altitude_bonus

        # Dome suppresses HR slightly
        if is_dome:
            hr_factor *= 0.95

        # Turf increases doubles/triples
        double_factor = 1.1 if surface == "turf" else 1.0
        triple_factor = 1.15 if surface == "turf" else 1.0

        # Deep CF = more triples
        if cf > 405:
            triple_factor *= 1.1

        # Foul territory affects batting average
        hit_factor = 1.0
        if foul_territory == "large":
            hit_factor = 0.97  # more foul outs
        elif foul_territory == "small":
            hit_factor = 1.03  # fewer foul outs

        # Altitude boosts everything slightly
        hit_factor *= (1.0 + altitude / 50000)

        return cls(
            hr_factor=round(hr_factor, 3),
            double_factor=round(double_factor, 3),
            triple_factor=round(triple_factor, 3),
            hit_factor=round(hit_factor, 3),
            so_factor=round(1.0 / hit_factor, 3),
        )


def _generate_weather(month: int = None, is_dome: bool = False) -> dict:
    """Generate random weather for a game.

    Returns: {temp: int, wind_direction: str, wind_speed: int, humidity: float, is_day_game: bool}
    """
    if is_dome:
        # Domes always have neutral weather
        return {
            "temp": 72,
            "wind_direction": "calm",
            "wind_speed": 0,
            "humidity": 0.50,
            "is_day_game": random.random() < 0.20
        }

    # Temperature varies by month
    if month is None:
        month = random.randint(1, 12)

    # April = cooler, July = hotter
    month_temp_offsets = {
        1: -10, 2: -8, 3: -3, 4: 5, 5: 12, 6: 18,
        7: 22, 8: 21, 9: 15, 10: 8, 11: 0, 12: -8
    }
    base_temp = 65 + month_temp_offsets.get(month, 0)
    temp = int(random.gauss(base_temp, 5))
    temp = max(45, min(95, temp))  # Clamp 45-95F

    # Wind
    wind_directions = ["in", "out", "crossfield", "calm", "calm"]  # calm is weighted
    wind_direction = random.choice(wind_directions)
    wind_speed = random.randint(0, 25) if wind_direction != "calm" else 0

    # Humidity
    humidity = random.uniform(0.30, 0.90)

    # Day/night: 20% day games on weekdays, 40% on weekends
    # For simplicity, use 20% as default, 40% if it's a weekend
    day_prob = 0.20
    is_day_game = random.random() < day_prob

    return {
        "temp": temp,
        "wind_direction": wind_direction,
        "wind_speed": wind_speed,
        "humidity": humidity,
        "is_day_game": is_day_game
    }


def _apply_weather_modifiers(batter_mod_dict: dict, pitcher_mod_dict: dict,
                             weather: dict, park: ParkFactors) -> tuple:
    """Apply weather modifiers to park factors and batting/pitching ratings.

    Returns: (modified_park_factors, batter_rating_mod, pitcher_rating_mod)
    """
    temp = weather.get("temp", 72)
    wind_direction = weather.get("wind_direction", "calm")
    wind_speed = weather.get("wind_speed", 0)
    humidity = weather.get("humidity", 0.50)

    # Create modified park factors
    mod_park = ParkFactors(
        hr_factor=park.hr_factor,
        double_factor=park.double_factor,
        triple_factor=park.triple_factor,
        hit_factor=park.hit_factor,
        so_factor=park.so_factor
    )

    # Temperature effects
    if temp < 50:
        mod_park.hr_factor *= 0.95  # -5% HR
        mod_park.double_factor *= 0.97  # -3% extra base hits
    elif temp > 85:
        mod_park.hr_factor *= 1.05  # +5% HR
        mod_park.double_factor *= 1.02  # +2% extra base hits

    # Wind effects
    wind_mod = 1.0
    if wind_direction == "out":
        wind_mod = 1.0 + (wind_speed / 5 * 0.08)  # +8% HR per 5mph out
        mod_park.hr_factor *= wind_mod
    elif wind_direction == "in":
        wind_mod = 1.0 - (wind_speed / 5 * 0.08)  # -8% HR per 5mph in
        mod_park.hr_factor *= wind_mod

    # Humidity effects
    if humidity >= 0.80:
        mod_park.hr_factor *= 1.02  # +2% HR from better ball carry

    # Batter rating modifiers for day/night
    batter_mod = 0
    if weather.get("is_day_game"):
        batter_mod = 1.02  # +2% contact in day games (better visibility)
    else:
        # Night games increase strikeouts slightly
        pass  # handled in pitcher mods

    # Pitcher rating modifiers
    pitcher_mod = 0
    if not weather.get("is_day_game"):
        pitcher_mod = 1.03  # +3% strikeout rate in night games (harder to see breaking balls)

    return mod_park, batter_mod, pitcher_mod


def _rating_to_prob(rating: int, baseline: float) -> float:
    """Convert a 20-80 rating to a probability modifier.
    50 = league average = baseline probability.
    Each point above/below 50 shifts probability proportionally.
    """
    # Sigmoid-ish curve centered at 50
    # 20 rating -> ~0.6x baseline, 80 rating -> ~1.5x baseline
    modifier = 1.0 + (rating - 50) * 0.0167
    return baseline * max(0.3, min(2.0, modifier))


def _platoon_adjustment(batter_bats: str, pitcher_throws: str,
                        platoon_split_json: str = None) -> tuple:
    """Calculate platoon adjustments for contact and power.

    Returns: (contact_modifier, power_modifier) based on batter hand vs pitcher hand.
    If platoon_split_json provided, uses per-player data; otherwise uses defaults.
    """
    contact_mod = 1.0
    power_mod = 1.0

    # If player has custom platoon splits, use them
    if platoon_split_json:
        try:
            splits = json.loads(platoon_split_json)
            # Determine which split applies (vs LHP or RHP)
            vs_key = "vs_lhp" if pitcher_throws == "L" else "vs_rhp"
            if vs_key in splits:
                split_data = splits[vs_key]
                # Splits are stored as +5 for +5% bonus
                contact_mod = 1.0 + (split_data.get("contact", 0) / 100.0)
                power_mod = 1.0 + (split_data.get("power", 0) / 100.0)
                return contact_mod, power_mod
        except (json.JSONDecodeError, TypeError):
            pass

    # Default platoon adjustments
    if batter_bats == "S":
        contact_mod = 1.01
        power_mod = 1.01
    elif (batter_bats == "L" and pitcher_throws == "R") or \
         (batter_bats == "R" and pitcher_throws == "L"):
        # Natural advantage: LHB vs RHP = +3 contact, +2 power
        # RHB vs LHP = +2 contact, +3 power
        if batter_bats == "L":
            contact_mod = 1.03
            power_mod = 1.02
        else:
            contact_mod = 1.02
            power_mod = 1.03
    else:
        # Same hand disadvantage
        contact_mod = 0.97
        power_mod = 0.97

    return contact_mod, power_mod


def _fatigue_modifier(pitcher: PitcherStats) -> float:
    """Pitcher effectiveness degrades with pitch count and carryover fatigue.
    Stamina rating determines when fatigue kicks in.
    Uses a two-phase curve: gradual decline then steep drop-off.
    Carryover fatigue from recent games causes pitchers to tire faster.
    """
    # Phase 1 threshold: mild fatigue begins
    # Stamina 80 = ~105 pitches, Stamina 30 = ~60 pitches
    mild_threshold = 40 + pitcher.stamina * 0.8  # 64-104 range

    # Phase 2 threshold: severe fatigue (arm is dead)
    # Stamina 80 = ~120 pitches, Stamina 30 = ~75 pitches
    severe_threshold = mild_threshold + 15

    # Carryover fatigue reduces the thresholds (fatigued pitchers tire faster)
    avg_carryover = (pitcher.fatigue_stuff_modifier + pitcher.fatigue_control_modifier) / 2.0
    if avg_carryover < 1.0:
        # e.g., avg 0.85 -> thresholds reduced by 15%
        mild_threshold *= avg_carryover
        severe_threshold *= avg_carryover

    if pitcher.pitches < mild_threshold:
        return 1.0

    overage = pitcher.pitches - mild_threshold

    if pitcher.pitches < severe_threshold:
        # Phase 1: gradual decline, ~1.5% per pitch over threshold
        return max(0.75, 1.0 - overage * 0.015)
    else:
        # Phase 2: steep drop-off, ~3% per pitch - pitcher is gassed
        severe_overage = pitcher.pitches - severe_threshold
        base = max(0.75, 1.0 - (severe_threshold - mild_threshold) * 0.015)
        return max(0.40, base - severe_overage * 0.03)


def _pitch_characteristics(pitch_type: str) -> dict:
    """Return characteristics for each pitch type.

    Pitch types: 4SFB (4-seam), 2SFB (2-seam), CUT (cutter), SI (sinker),
                 SL (slider), CB (curveball), CH (changeup), SPL (splitter),
                 KC (knuckle curve), SW (sweeper), SC (screwball), KN (knuckleball)
    """
    characteristics = {
        "4SFB": {
            "contact": 0.95, "strikeout": 1.0, "hr": 1.10, "contact_quality": 0.90,
            "gb_rate_mod": 0.95, "babip_mod": 1.0, "usage": 0.35, "base_velocity": 94.0
        },
        "2SFB": {
            "contact": 0.90, "strikeout": 0.95, "hr": 0.95, "contact_quality": 0.85,
            "gb_rate_mod": 1.15, "babip_mod": 0.98, "usage": 0.15, "base_velocity": 93.0
        },
        "CUT": {
            "contact": 0.88, "strikeout": 1.05, "hr": 0.85, "contact_quality": 0.92,
            "gb_rate_mod": 1.05, "babip_mod": 0.95, "usage": 0.12, "base_velocity": 89.0
        },
        "SI": {
            "contact": 0.85, "strikeout": 0.92, "hr": 0.80, "contact_quality": 0.80,
            "gb_rate_mod": 1.20, "babip_mod": 0.93, "usage": 0.12, "base_velocity": 93.0
        },
        "SL": {
            "contact": 0.80, "strikeout": 1.20, "hr": 0.75, "contact_quality": 0.95,
            "gb_rate_mod": 0.90, "babip_mod": 1.0, "usage": 0.15, "base_velocity": 85.0
        },
        "CB": {
            "contact": 0.78, "strikeout": 1.15, "hr": 0.70, "contact_quality": 0.95,
            "gb_rate_mod": 0.95, "babip_mod": 1.02, "usage": 0.10, "base_velocity": 79.0
        },
        "CH": {
            "contact": 0.88, "strikeout": 1.08, "hr": 0.82, "contact_quality": 0.88,
            "gb_rate_mod": 1.05, "babip_mod": 0.97, "usage": 0.08, "base_velocity": 85.0
        },
        "SPL": {
            "contact": 0.75, "strikeout": 1.12, "hr": 0.65, "contact_quality": 0.93,
            "gb_rate_mod": 1.00, "babip_mod": 0.98, "usage": 0.06, "base_velocity": 86.0
        },
        "KC": {
            "contact": 0.82, "strikeout": 1.18, "hr": 0.72, "contact_quality": 0.94,
            "gb_rate_mod": 0.98, "babip_mod": 1.0, "usage": 0.04, "base_velocity": 78.0
        },
        "SW": {
            "contact": 0.80, "strikeout": 1.08, "hr": 0.78, "contact_quality": 0.92,
            "gb_rate_mod": 0.92, "babip_mod": 1.0, "usage": 0.03, "base_velocity": 82.0
        },
        "SC": {
            "contact": 0.79, "strikeout": 1.10, "hr": 0.75, "contact_quality": 0.94,
            "gb_rate_mod": 0.95, "babip_mod": 1.01, "usage": 0.02, "base_velocity": 80.0
        },
        "KN": {
            "contact": 0.85, "strikeout": 1.25, "hr": 0.90, "contact_quality": 0.85,
            "gb_rate_mod": 1.10, "babip_mod": 1.05, "usage": 0.02, "base_velocity": 78.0
        },
    }
    return characteristics.get(pitch_type, characteristics["4SFB"])


def _select_pitch_type(pitcher: PitcherStats, count: list, is_strikeout_situation: bool) -> str:
    """Select a pitch type based on count and pitcher's repertoire.

    Uses pitch_repertoire_json if available, otherwise falls back to legacy pitch_types.
    """
    # Try to use pitch_repertoire_json first
    if hasattr(pitcher, 'pitch_repertoire') and pitcher.pitch_repertoire:
        # pitcher.pitch_repertoire should be a list of dicts with 'type', 'rating', 'usage'
        pitches_by_rating = sorted(pitcher.pitch_repertoire, key=lambda x: x.get('rating', 50), reverse=True)

        # Strikeout situation (2 strikes): use best secondary
        if is_strikeout_situation and len(pitches_by_rating) > 1:
            if random.random() < 0.7 and pitches_by_rating[1]['type'] not in ("4SFB", "2SFB", "SI"):
                return pitches_by_rating[1]['type']

        # Behind in count: favor fastball types
        if count[0] > count[1]:
            fastballs = [p for p in pitches_by_rating if p['type'] in ("4SFB", "2SFB", "SI")]
            if fastballs:
                return fastballs[0]['type']

        # Ahead in count: mix in breaking balls
        if count[1] > count[0]:
            if random.random() < 0.6:
                secondary = [p for p in pitches_by_rating if p['type'] not in ("4SFB", "2SFB", "SI")]
                if secondary:
                    return secondary[0]['type']

        # Weighted selection by usage rates
        total_usage = sum(p.get('usage', 0.05) for p in pitches_by_rating)
        if total_usage > 0:
            r = random.uniform(0, total_usage)
            cumulative = 0
            for pitch_data in pitches_by_rating:
                cumulative += pitch_data.get('usage', 0.05)
                if r <= cumulative:
                    return pitch_data['type']

        return pitches_by_rating[0]['type'] if pitches_by_rating else "4SFB"

    # Legacy fallback: use pitch_types tuples
    if not pitcher.pitch_types:
        return "4SFB"

    pitches_by_rating = sorted(pitcher.pitch_types, key=lambda x: x[1], reverse=True)

    # Strikeout situation (2 strikes): use best secondary
    if is_strikeout_situation and len(pitches_by_rating) > 1:
        if random.random() < 0.7 and pitches_by_rating[1][0] not in ("4SFB", "2SFB", "SI", "FB"):
            return pitches_by_rating[1][0]

    # Behind in count (more balls than strikes): favor fastball
    if count[0] > count[1]:
        fastballs = [p for p in pitches_by_rating if p[0] in ("4SFB", "2SFB", "SI", "FB")]
        if fastballs:
            return fastballs[0][0]

    # Ahead in count: mix in breaking balls
    if count[1] > count[0]:
        if random.random() < 0.6:
            secondary = [p for p in pitches_by_rating if p[0] not in ("4SFB", "2SFB", "SI", "FB")]
            if secondary:
                return secondary[0][0]

    # Even count or default: weighted by effectiveness
    total_rating = sum(p[1] for p in pitches_by_rating)
    r = random.uniform(0, total_rating)
    cumulative = 0
    for pitch_type, rating in pitches_by_rating:
        cumulative += rating
        if r <= cumulative:
            return pitch_type

    return pitches_by_rating[0][0]


def _pitch_type_modifier(pitch_type: str, is_fastball_count: bool) -> dict:
    """Return probability modifiers for each pitch type."""
    chars = _pitch_characteristics(pitch_type)
    return {
        "contact": chars.get("contact", 0.95),
        "strikeout": chars.get("strikeout", 1.0),
        "hr": chars.get("hr", 1.0),
        "contact_quality": chars.get("contact_quality", 0.90)
    }


def calculate_win_expectancy(inning: int, score_diff: int, outs: int,
                            runners_on: int = 0) -> float:
    """Calculate win expectancy from the HOME team's perspective.

    Uses a simplified model based on historical MLB win expectancy data.

    Args:
        inning: Current inning (1-9+)
        score_diff: Home score minus away score (positive = home leads)
        outs: Number of outs in current half-inning (0-2)
        runners_on: Bitmask (1=1st, 2=2nd, 4=3rd)

    Returns:
        Win probability for home team, 0.0-100.0
    """
    # Base WE: home team wins ~54% at start due to home field advantage
    # Sigmoid function centered on score_diff, steeper in later innings
    inning_factor = min(inning, 9) / 9.0  # 0.11 to 1.0

    # Steepness increases as game progresses (late innings more decisive)
    steepness = 0.3 + inning_factor * 0.7  # 0.41 to 1.0

    # Score diff impact: each run matters more in later innings
    run_impact = score_diff * steepness

    # Sigmoid: 1 / (1 + e^(-k*x))
    # k controls how steep the curve is
    k = 0.4 + inning_factor * 0.6  # more decisive late
    we = 1.0 / (1.0 + math.exp(-k * run_impact))

    # Home field advantage baseline (adds ~4% in early innings, less late)
    home_advantage = 0.04 * (1.0 - inning_factor * 0.5)
    we += home_advantage

    # Runner adjustment: runners on base shift WE toward the batting team
    runner_bonus = 0
    if runners_on & 1:  # runner on first
        runner_bonus += 0.02
    if runners_on & 2:  # runner on second
        runner_bonus += 0.04
    if runners_on & 4:  # runner on third
        runner_bonus += 0.06

    # Outs adjustment: more outs = less opportunity
    outs_factor = 1.0 - outs * 0.3  # 1.0, 0.7, 0.4
    runner_bonus *= outs_factor

    # In bottom half, runners help home team; in top half, they help away
    # (simplified: assume we don't know which half, slight home bias)
    we += runner_bonus * 0.3

    # 9th inning or later with large deficit: compress toward 0 or 100
    if inning >= 9:
        if score_diff >= 1 and outs == 2:
            we = max(we, 0.90 + score_diff * 0.02)
        elif score_diff <= -4:
            we = min(we, 0.05 - abs(score_diff + 4) * 0.01)

    return round(max(0.1, min(99.9, we * 100)), 1)


def get_strike_zone_factor(height_inches: int) -> float:
    """Return a strike zone multiplier based on player height.

    Baseline: 73 inches (6'1") = 1.0
    Each inch above/below adjusts by ~0.01
    Taller batters have bigger zones (more strikes called).
    Shorter batters have smaller zones (more balls).
    Returns value in range 0.92 to 1.08.
    """
    baseline = 73
    diff = height_inches - baseline
    factor = 1.0 + diff * 0.01
    return max(0.92, min(1.08, factor))


def _resolve_pitch(batter: BatterStats, pitcher: PitcherStats, count: list,
                  park: ParkFactors, leverage: float = 1.0, weather: dict = None,
                  pitcher_team_chemistry: int = 50) -> tuple:
    """Resolve a single pitch.
    Returns: (result, pitch_type, velocity, zone) where result is one of:
    'ball', 'called_strike', 'swinging_strike', 'foul', 'hbp', 'in_play'
    """
    fatigue = _fatigue_modifier(pitcher)
    contact_mod, power_mod = _platoon_adjustment(batter.bats, pitcher.throws, batter.platoon_split_json)

    # Get pitch type
    is_strikeout_sit = count[1] >= 2
    pitch_type = _select_pitch_type(pitcher, count, is_strikeout_sit)
    pitch_mod = _pitch_type_modifier(pitch_type, count[0] > count[1])

    # Calculate velocity for this pitch
    chars = _pitch_characteristics(pitch_type)
    base_velo = chars.get("base_velocity", 93.0)
    # Adjust velocity by pitcher stuff rating and fatigue
    velo_adj = (pitcher.stuff - 50) * 0.15  # +/- up to ~4.5 mph
    fatigue_velo = fatigue * pitcher.fatigue_stuff_modifier
    velocity = round(base_velo + velo_adj + random.gauss(0, 1.0), 1)
    velocity = round(velocity * fatigue_velo, 1)

    # Home field advantage: slight boost to home batters (~2% contact/power, better eye)
    home_boost = 1.02 if batter.is_home else 1.0

    # Apply carryover fatigue separately to stuff and control
    effective_stuff = pitcher.stuff * fatigue * pitcher.fatigue_stuff_modifier
    effective_control = pitcher.control * fatigue * pitcher.fatigue_control_modifier

    # Control rating with chemistry modifier determines zone accuracy
    adjusted_control = _apply_chemistry_control_modifier(int(effective_control), pitcher_team_chemistry)
    pitcher_control_mod = _rating_to_prob(adjusted_control, 1.0)
    pitcher_stuff_mod = _rating_to_prob(int(effective_stuff), 1.0) * pitch_mod["strikeout"]
    batter_contact_mod = _rating_to_prob(batter.contact, 1.0) * contact_mod * home_boost

    # Eye/plate discipline factor: affects zone recognition and chase rate
    # High eye = better at recognizing balls (more walks, fewer Ks on bad pitches)
    eye_mod = _rating_to_prob(batter.eye, 1.0)  # 0.6-1.4 range

    # Individual batter strike zone factor based on height
    # Taller batters have bigger zones (more strikes), shorter batters smaller zones (more balls)
    sz_factor = get_strike_zone_factor(batter.height_inches)

    # Strike zone probability (affected by control, count, and batter height)
    in_zone_prob = 0.65 * pitcher_control_mod * sz_factor
    if count[1] >= 2:  # two strikes, pitcher ahead
        in_zone_prob = 0.75 * sz_factor  # strike zone expands
    elif count[0] >= 2:  # hitter ahead
        in_zone_prob = 0.55 * sz_factor  # pitcher avoids zone

    # Generate zone for this pitch
    # Zones 1-9: strike zone quadrants (3x3 grid, top-left=1 to bottom-right=9)
    # Zones 11-14: chase zones (11=up, 12=down, 13=inside, 14=outside)
    # Decide: ball or pitch in zone
    if random.random() > in_zone_prob:
        # Ball - assign a chase zone
        zone = random.choice([11, 12, 13, 14])
        return ("ball", pitch_type, velocity, zone)

    # In the strike zone - assign zone 1-9
    zone = random.randint(1, 9)

    # Pitch in zone: swing or take?
    # High-eye batters are more selective (lower swing rate on marginal pitches)
    # Low-eye batters chase more aggressively
    eye_swing_adj = (50 - batter.eye) * 0.003  # high eye = less swing, low = more swing
    swing_prob = 0.55 + (50 - batter.contact) * 0.005 + count[1] * 0.1 + eye_swing_adj
    swing_prob = max(0.3, min(0.9, swing_prob))

    if random.random() > swing_prob:
        return ("called_strike", pitch_type, velocity, zone)

    # Batter swings
    # Swinging strike vs contact (eye helps avoid chasing bad pitches that sneak into zone)
    eye_contact_bonus = 1.0 + (batter.eye - 50) * 0.002  # high eye = slightly better contact
    contact_prob = _rating_to_prob(batter.contact, 0.65) * pitch_mod["contact"] * eye_contact_bonus
    contact_prob = max(0.2, min(0.95, contact_prob))

    if random.random() > contact_prob:
        return ("swinging_strike", pitch_type, velocity, zone)

    # Contact made: foul or in play?
    foul_prob = 0.25
    if count[1] >= 2:
        foul_prob = 0.15  # fewer fouls with 2 strikes

    if random.random() < foul_prob:
        return ("foul", pitch_type, velocity, zone)

    # Ball in play
    return ("in_play", pitch_type, velocity, zone)


def _resolve_batted_ball(batter: BatterStats, pitcher: PitcherStats, park: ParkFactors,
                        count: list, runners_on: int, outs: int, leverage: float = 1.0,
                        weather: dict = None) -> str:
    """Resolve outcome of a ball in play."""
    fatigue = _fatigue_modifier(pitcher)
    contact_mod, power_mod = _platoon_adjustment(batter.bats, pitcher.throws, batter.platoon_split_json)

    # Apply morale modifiers to contact and power ratings
    morale_contact_mult, morale_power_mult = _apply_morale_modifier(batter)

    # Home field advantage: slight power and contact boost for home batters
    home_boost = 1.02 if batter.is_home else 1.0

    # Apply carryover fatigue to stuff rating
    effective_stuff = pitcher.stuff * fatigue * pitcher.fatigue_stuff_modifier
    pitcher_stuff_mod = _rating_to_prob(int(effective_stuff), 1.0)
    batter_contact_mod = _rating_to_prob(batter.contact * morale_contact_mult, 1.0) * contact_mod * home_boost
    batter_power_mod = _rating_to_prob(batter.power * morale_power_mult, 1.0) * power_mod * home_boost
    batter_speed_mod = _rating_to_prob(batter.speed, 1.0)

    # Base probabilities — MLB batted ball distribution: ~44% GB, ~35% FB, ~21% LD
    hr_prob = batter_power_mod * 0.033 * park.hr_factor / pitcher_stuff_mod
    double_prob = batter_power_mod * 0.045 * park.double_factor * 0.8 * power_mod
    triple_prob = batter_speed_mod * 0.005 * park.triple_factor * contact_mod
    single_prob = batter_contact_mod * 0.150 * park.hit_factor / pitcher_stuff_mod
    go_prob = 0.19   # ground ball outs (~44% of BIP, ~73% become outs)
    fo_prob = 0.14   # fly ball outs (~35% of BIP, ~85% become outs, minus HR)
    ld_prob = 0.11   # line drive outs (~21% of BIP, ~26% become outs)

    # Clutch adjustment: enhanced for high-leverage situations
    if leverage > 1.2:
        clutch_bonus = (batter.clutch - 50) * 0.001  # -0.05 to +0.05 range
        hr_prob *= (1.0 + clutch_bonus)
        single_prob *= (1.0 + clutch_bonus)
        double_prob *= (1.0 + clutch_bonus)

    # Normalize
    total = hr_prob + double_prob + triple_prob + single_prob + go_prob + fo_prob + ld_prob
    r = random.random() * total

    cumulative = 0
    for outcome, prob in [
        ("HR", hr_prob), ("3B", triple_prob), ("2B", double_prob),
        ("1B", single_prob), ("GO", go_prob), ("FO", fo_prob), ("LD", ld_prob)
    ]:
        cumulative += prob
        if r < cumulative:
            return outcome

    return "FO"


def _apply_morale_modifier(batter: BatterStats) -> tuple:
    """Apply morale rating modifiers to contact and power ratings.
    Returns (contact_multiplier, power_multiplier).
    Morale 0-30: -3 contact, -3 power
    Morale 50: neutral (1.0x)
    Morale 70-100: +3 contact, +3 power
    """
    contact_delta = (batter.morale - 50) * 0.06  # -3 to +3 range
    power_delta = (batter.morale - 50) * 0.06    # -3 to +3 range

    return (1.0 + contact_delta / 50, 1.0 + power_delta / 50)


def _is_leverage_situation(runners_on: int, outs: int, inning: int,
                          home_score: int, away_score: int) -> bool:
    """Check if this is a high-leverage situation for clutch activation.
    High-leverage: runners in scoring position AND (7th inning+ OR score diff <= 2)
    """
    runners_in_scoring_position = runners_on > 0
    late_game = inning >= 7
    close_game = abs(home_score - away_score) <= 2

    return runners_in_scoring_position and (late_game or close_game)


def _apply_chemistry_control_modifier(pitcher_control: int, team_chemistry: int) -> int:
    """Apply team chemistry modifier to pitcher control.
    Chemistry > 70: +1 control
    Chemistry < 30: -1 control
    Chemistry 30-70: proportional scaling
    """
    if team_chemistry > 70:
        return min(80, pitcher_control + 1)
    elif team_chemistry < 30:
        return max(20, pitcher_control - 1)
    return pitcher_control


def _resolve_at_bat_with_count(batter: BatterStats, pitcher: PitcherStats,
                               park: ParkFactors, runners_on: int = 0,
                               outs: int = 0, leverage: float = 1.0, weather: dict = None,
                               pitcher_team_chemistry: int = 50) -> tuple:
    """
    Resolve a single plate appearance with pitch-by-pitch count tracking.
    Returns (outcome, pitches_thrown) where pitches_thrown is a list of
    (result, pitch_type, velocity, zone, count_balls, count_strikes) tuples.
    """
    count = [0, 0]  # [balls, strikes]
    pitches_thrown = []

    while True:
        # Resolve this pitch - returns (result, pitch_type, velocity, zone)
        pitch_result = _resolve_pitch(batter, pitcher, count, park, leverage, weather, pitcher_team_chemistry)
        result, p_type, p_velo, p_zone = pitch_result
        # Store pitch detail with count at time of pitch
        pitches_thrown.append((result, p_type, p_velo, p_zone, count[0], count[1]))
        # Count EVERY pitch toward fatigue (including terminal pitches)
        pitcher.pitches += 1

        if result == "ball":
            count[0] += 1
            if count[0] >= 4:
                return "BB", pitches_thrown

        elif result in ("called_strike", "swinging_strike"):
            count[1] += 1
            if count[1] >= 3:
                return "SO", pitches_thrown

        elif result == "foul":
            # Foul doesn't increase strike count unless already 2 strikes
            if count[1] < 2:
                count[1] += 1
            # Otherwise foul just stays in play

        elif result == "hbp":
            return "HBP", pitches_thrown

        elif result == "in_play":
            # Resolve batted ball outcome
            outcome = _resolve_batted_ball(batter, pitcher, park, count, runners_on, outs, leverage, weather)
            return outcome, pitches_thrown


@dataclass
class BaseState:
    first: int = 0   # player_id or 0
    second: int = 0
    third: int = 0

    def runners_on(self) -> int:
        return (1 if self.first else 0) + (1 if self.second else 0) + (1 if self.third else 0)

    def clear(self):
        self.first = self.second = self.third = 0


def _advance_runners(bases: BaseState, outcome: str, batter_id: int,
                     batter_speed: int, lineup: list[BatterStats] = None) -> int:
    """Advance runners based on hit outcome. Returns runs scored.
    When lineup is provided, increments runs on the BatterStats for each scorer.
    """
    runs = 0
    scorers = []  # player_ids that scored

    if outcome == "HR":
        # Everyone on base scores, plus the batter
        if bases.third:
            scorers.append(bases.third)
        if bases.second:
            scorers.append(bases.second)
        if bases.first:
            scorers.append(bases.first)
        scorers.append(batter_id)
        runs = len(scorers)
        bases.clear()
    elif outcome == "3B":
        if bases.third:
            scorers.append(bases.third)
            runs += 1
        if bases.second:
            scorers.append(bases.second)
            runs += 1
        if bases.first:
            scorers.append(bases.first)
            runs += 1
        bases.clear()
        bases.third = batter_id
    elif outcome == "2B":
        if bases.third:
            scorers.append(bases.third)
            runs += 1
        if bases.second:
            scorers.append(bases.second)
            runs += 1
        bases.third = bases.first if bases.first and random.random() < 0.6 else 0
        if bases.first and not bases.third:
            scorers.append(bases.first)
            runs += 1
        bases.second = batter_id
        bases.first = 0
    elif outcome == "1B":
        if bases.third:
            scorers.append(bases.third)
            runs += 1
        if bases.second:
            if random.random() < 0.4 + batter_speed * 0.003:
                scorers.append(bases.second)
                runs += 1
            else:
                bases.third = bases.second
        elif bases.first:
            bases.third = 0
        if bases.first:
            bases.second = bases.first
        else:
            bases.second = 0
        bases.first = batter_id
    elif outcome in ("BB", "HBP"):
        if bases.first and bases.second and bases.third:
            scorers.append(bases.third)
            runs += 1
        if bases.first and bases.second:
            bases.third = bases.second
        if bases.first:
            bases.second = bases.first
        bases.first = batter_id
    elif outcome == "SF":
        if bases.third:
            scorers.append(bases.third)
            runs += 1
            bases.third = 0
    elif outcome == "WP":
        # Wild pitch / passed ball: runners advance one base, batter stays at plate
        if bases.third:
            scorers.append(bases.third)
            runs += 1
            bases.third = 0
        if bases.second:
            bases.third = bases.second
            bases.second = 0
        if bases.first:
            bases.second = bases.first
            bases.first = 0
    elif outcome == "E":
        # Reached on error: advance runners like a single
        if bases.third:
            scorers.append(bases.third)
            runs += 1
        if bases.second:
            bases.third = bases.second
        if bases.first:
            bases.second = bases.first
        bases.first = batter_id

    # Credit runs scored to individual batters in the lineup
    if lineup and scorers:
        lineup_by_id = {b.player_id: b for b in lineup}
        for scorer_id in scorers:
            if scorer_id in lineup_by_id:
                lineup_by_id[scorer_id].runs += 1

    return runs


def _calculate_dp_chance(runner_speed: int, batter_speed: int) -> float:
    """Calculate double play probability based on runner and batter speed."""
    base_rate = 0.50
    if runner_speed >= 70:
        base_rate = 0.30
    elif runner_speed <= 30:
        base_rate = 0.65
    else:
        base_rate = 0.65 - (runner_speed - 30) * (0.35 / 40)

    batter_mod = 1.0 + (50 - batter_speed) * 0.005
    base_rate *= max(0.15, min(1.5, batter_mod))

    return max(0.10, min(0.75, base_rate))


def _calculate_error_probability(fielding_rating: int, is_ground_ball: bool = True,
                                 position: str = None, batter_speed: int = 50) -> float:
    """Calculate error probability on a batted ball.
    Accounts for play type, fielder position, and batter speed pressure.
    """
    if is_ground_ball:
        # Ground balls: position-adjusted base rate
        pos_rates = {"SS": 0.025, "3B": 0.022, "2B": 0.018, "1B": 0.008,
                     "C": 0.010, "P": 0.015}
        base_rate = pos_rates.get(position, 0.018)
        # Fielding adjustment: 80 rating = 0.5x errors, 20 rating = 2x errors
        fielding_mod = 2.0 - (fielding_rating / 50)
        base_rate *= max(0.3, fielding_mod)
        # Fast runners create more pressure (+20% for 70+ speed)
        if batter_speed >= 70:
            base_rate *= 1.2
        elif batter_speed >= 60:
            base_rate *= 1.1
    else:
        # Fly balls: very rare errors, OF position matters
        base_rate = 0.003 * (2.0 - fielding_rating / 50)

    return max(0.001, min(0.08, base_rate))


def _calculate_leverage(inning: int, outs: int, score_diff: int,
                        bases: 'BaseState') -> float:
    """Calculate leverage index based on game situation.
    Approximation of Tom Tango's leverage index.
    Returns float from 0.1 (blowout) to ~3.5 (bases loaded, tie game, 9th).
    """
    # Base leverage by inning
    if inning <= 3:
        inning_mult = 0.7
    elif inning <= 6:
        inning_mult = 1.0
    elif inning <= 8:
        inning_mult = 1.5
    else:  # 9th+
        inning_mult = 2.0

    # Score differential: close games = high leverage
    if score_diff == 0:
        score_mult = 1.5
    elif score_diff <= 1:
        score_mult = 1.3
    elif score_diff <= 2:
        score_mult = 1.1
    elif score_diff <= 3:
        score_mult = 0.8
    elif score_diff <= 5:
        score_mult = 0.5
    else:
        score_mult = 0.2  # Blowout

    # Runners on base increase leverage
    runners = bases.runners_on()
    if runners == 0:
        runner_mult = 0.8
    elif runners == 1:
        runner_mult = 1.1
    elif runners == 2:
        runner_mult = 1.4
    else:
        runner_mult = 1.8  # Bases loaded

    # Fewer outs = higher leverage
    out_mult = 1.0 + (2 - outs) * 0.15

    leverage = inning_mult * score_mult * runner_mult * out_mult
    return max(0.1, min(3.5, leverage))


def _check_wild_pitch(pitcher: 'PitcherStats', bases: 'BaseState',
                      catcher_fielding: int = 50) -> bool:
    """Check if a wild pitch occurs. ~2-3% chance per pitch with runners on,
    modified by pitcher control and catcher fielding.
    """
    if not bases.runners_on():
        return False  # WP only matters with runners on base
    # Base rate: ~0.8% per at-bat (~0.15% per pitch, but we check per AB)
    base_rate = 0.008
    # Poor control increases WP
    control_mod = max(0.3, (80 - pitcher.control) / 40)
    # Catcher fielding reduces WP
    catcher_mod = max(0.5, (80 - catcher_fielding) / 40)
    # Fatigue increases WP
    fatigue_mod = 1.0 + max(0, (pitcher.pitches - 80)) * 0.005
    rate = base_rate * control_mod * catcher_mod * fatigue_mod
    return random.random() < min(rate, 0.04)


def _check_passed_ball(catcher_fielding: int, bases: 'BaseState') -> bool:
    """Check if a passed ball occurs. Rarer than wild pitches.
    ~0.3% chance per at-bat, modified by catcher fielding.
    """
    if not bases.runners_on():
        return False
    base_rate = 0.003
    # Poor catchers have more passed balls
    catcher_mod = max(0.3, (80 - catcher_fielding) / 40)
    rate = base_rate * catcher_mod
    return random.random() < min(rate, 0.02)


def _assign_fielding_credit(outcome: str, defensive_lineup: list, outs_recorded: int = 1):
    """Assign putouts and assists to fielders based on the play type."""
    if not defensive_lineup or outs_recorded < 1:
        return
    # Pick a fielder based on play type
    infielders = [b for b in defensive_lineup if b.position in ("SS", "2B", "3B", "1B", "C")]
    outfielders = [b for b in defensive_lineup if b.position in ("LF", "CF", "RF")]
    first_basemen = [b for b in defensive_lineup if b.position == "1B"]

    if outcome == "GO":
        # Ground out: infielder gets assist, 1B gets putout
        if infielders:
            random.choice(infielders).assists += 1
        if first_basemen:
            first_basemen[0].putouts += 1
        elif infielders:
            infielders[0].putouts += 1
    elif outcome == "FO" or outcome == "SF":
        # Fly out / sac fly: outfielder gets putout
        if outfielders:
            random.choice(outfielders).putouts += 1
        elif infielders:
            random.choice(infielders).putouts += 1
    elif outcome == "LD":
        # Line drive out: ~40% caught by infielder, ~60% caught by outfielder
        if random.random() < 0.4 and infielders:
            random.choice(infielders).putouts += 1
        elif outfielders:
            random.choice(outfielders).putouts += 1
        elif infielders:
            random.choice(infielders).putouts += 1
    elif outcome == "SO":
        # Strikeout: catcher gets putout
        catchers = [b for b in defensive_lineup if b.position == "C"]
        if catchers:
            catchers[0].putouts += 1


def _attempt_stolen_base(bases: BaseState, outs: int, lineup: list[BatterStats],
                         pitcher: PitcherStats, steal_multiplier: float = 1.0) -> tuple:
    """Attempt a stolen base before the at-bat.
    Returns (did_attempt, did_succeed, outs_added).
    """
    if outs >= 2:
        return False, False, 0

    # Identify the lead runner eligible to steal
    runner_id = 0
    stealing_base = None
    if bases.first and not bases.second:
        runner_id = bases.first
        stealing_base = "second"
    elif bases.second and not bases.third:
        runner_id = bases.second
        stealing_base = "third"
    else:
        return False, False, 0

    # Find the runner's BatterStats to get speed
    runner = None
    for b in lineup:
        if b.player_id == runner_id:
            runner = b
            break
    if not runner:
        return False, False, 0

    # Per-player steal aggression override (1-5 scale, 3=normal)
    player_steal_mult = {1: 0.0, 2: 0.5, 3: 1.0, 4: 1.5, 5: 2.0}.get(
        runner.steal_aggression, 1.0)
    # Attempt probability: 8% base * (speed / 50) * steal_multiplier * player_mult
    attempt_prob = 0.08 * (runner.speed / 50.0) * steal_multiplier * player_steal_mult
    if random.random() >= attempt_prob:
        return False, False, 0

    # Success rate: 65% base + (speed - 50) * 0.5%
    success_rate = 0.65 + (runner.speed - 50) * 0.005
    success_rate = max(0.35, min(0.95, success_rate))

    if random.random() < success_rate:
        # Success: advance runner
        runner.sb += 1
        if stealing_base == "second":
            bases.second = bases.first
            bases.first = 0
        elif stealing_base == "third":
            bases.third = bases.second
            bases.second = 0
        return True, True, 0
    else:
        # Caught stealing: runner is out
        runner.cs += 1
        if stealing_base == "second":
            bases.first = 0
        elif stealing_base == "third":
            bases.second = 0
        return True, False, 1


def _attempt_sac_bunt(batter: BatterStats, bases: BaseState, outs: int,
                      bunt_rate: float) -> bool:
    """Attempt a sacrifice bunt. Returns True if bunt attempted and executed."""
    if outs >= 2 or bunt_rate <= 0:
        return False
    if not bases.first and not bases.second:
        return False
    if batter.power >= 60:
        return False
    if random.random() >= bunt_rate:
        return False
    return True


def _attempt_hit_and_run(bases: BaseState, outs: int, batter: BatterStats,
                         hit_and_run_mult: float = 1.0) -> bool:
    """Attempt hit-and-run with runner on first, < 2 outs."""
    if outs >= 2:
        return False
    if not bases.first or bases.second or bases.third:
        return False
    if batter.contact < 40:
        return False

    # Base attempt rate: 5% with multiplier
    attempt_rate = 0.05 * hit_and_run_mult
    return random.random() < attempt_rate


def _apply_hit_and_run(pitcher: PitcherStats, batter: BatterStats,
                      park: ParkFactors) -> str:
    """Resolve outcome with hit-and-run active.
    Runner goes, batter must swing. Higher contact chance, lower power.
    """
    # Force swing, higher contact rate
    contact_mod_swing = 1.2  # Contact becomes more likely
    power_mod_swing = 0.7    # Power diminished

    # Simulate at-bat with modified ratings
    platoon_contact, platoon_power = _platoon_adjustment(batter.bats, pitcher.throws, batter.platoon_split_json)
    fatigue = _fatigue_modifier(pitcher)

    # Apply carryover fatigue to stuff rating
    effective_stuff = pitcher.stuff * fatigue * pitcher.fatigue_stuff_modifier
    pitcher_stuff_mod = _rating_to_prob(int(effective_stuff), 1.0)
    batter_contact_mod = _rating_to_prob(int(batter.contact * contact_mod_swing), 1.0) * platoon_contact
    batter_power_mod = _rating_to_prob(int(batter.power * power_mod_swing), 1.0) * platoon_power

    # Base probabilities with modifications
    hr_prob = batter_power_mod * 0.02 * park.hr_factor / pitcher_stuff_mod
    double_prob = batter_power_mod * 0.03 * park.double_factor * 0.8 * platoon_power
    triple_prob = 0.001  # Very unlikely on hit-and-run
    single_prob = batter_contact_mod * 0.18 * park.hit_factor / pitcher_stuff_mod
    go_prob = 0.22
    fo_prob = 0.10  # Must swing, can't take strikes
    ld_prob = 0.08  # Line drives on hit-and-run

    total = hr_prob + double_prob + triple_prob + single_prob + go_prob + fo_prob + ld_prob
    r = random.random() * total

    cumulative = 0
    for outcome, prob in [
        ("HR", hr_prob), ("3B", triple_prob), ("2B", double_prob),
        ("1B", single_prob), ("GO", go_prob), ("FO", fo_prob), ("LD", ld_prob)
    ]:
        cumulative += prob
        if r < cumulative:
            return outcome

    return "GO"


def _attempt_suicide_squeeze(bases: BaseState, outs: int, batter: BatterStats,
                            squeeze_mult: float = 1.0) -> bool:
    """Attempt suicide squeeze with runner on 3rd, < 2 outs."""
    if outs >= 2:
        return False
    if not bases.third:
        return False

    # Low power hitters more likely
    power_penalty = 1.0 - (batter.power - 40) * 0.01
    attempt_rate = 0.02 * squeeze_mult * max(0.1, power_penalty)
    return random.random() < attempt_rate


def _apply_suicide_squeeze(batter: BatterStats, pitcher: PitcherStats,
                          park: ParkFactors) -> str:
    """Resolve suicide squeeze. Must bunt successfully or runner is out."""
    # Bunt success heavily dependent on contact
    contact_mod = (batter.contact / 50.0) * 1.5
    bunt_success_rate = 0.3 * contact_mod
    bunt_success_rate = max(0.2, min(0.8, bunt_success_rate))

    if random.random() < bunt_success_rate:
        return "SAC"  # Successful bunt, runner scores
    else:
        return "SO"  # Failed bunt, runner likely caught at plate


def _attempt_intentional_walk(bases: BaseState, outs: int, batter: BatterStats,
                             next_batter: BatterStats = None,
                             ibb_threshold: int = 65) -> bool:
    """Attempt IBB on dangerous hitter when first base open, runner in scoring position.
    Uses composite threat score (contact + power + eye) instead of raw power alone.
    """
    if bases.first:
        return False  # First must be open
    if not (bases.second or bases.third):
        return False  # Need runner in scoring position
    # Never IBB with bases loaded
    if bases.first and bases.second and bases.third:
        return False

    # Composite threat: weighted average of offensive tools
    batter_threat = (batter.contact * 0.3 + batter.power * 0.5 + batter.eye * 0.2)

    if batter_threat < ibb_threshold:
        return False

    # Base IBB probability scales with how dangerous the batter is
    ibb_prob = 0.15 + (batter_threat - ibb_threshold) * 0.01

    # With 2 outs, IBB is less common (but not zero — protecting against XBH)
    if outs >= 2:
        ibb_prob *= 0.3

    # If next batter is significantly worse, IBB becomes much more likely
    if next_batter:
        next_threat = (next_batter.contact * 0.3 + next_batter.power * 0.5 +
                      next_batter.eye * 0.2)
        gap = batter_threat - next_threat
        if gap >= 20:
            ibb_prob = min(0.85, ibb_prob * 2.5)
        elif gap >= 10:
            ibb_prob = min(0.70, ibb_prob * 1.8)
        elif gap < 0:
            ibb_prob *= 0.3  # Next batter is better — don't walk this one

    # Runner on third with less than 2 outs: more likely to set up force/DP
    if bases.third and outs < 2:
        ibb_prob *= 1.3

    return random.random() < min(ibb_prob, 0.90)


def _attempt_defensive_shift(batter: BatterStats, shift_tendency: float = 0.5) -> bool:
    """Deploy defensive shift against pull-heavy hitters.
    Considers power/contact profile and team shift tendency setting.
    """
    # Pull tendency: high power + low contact = pull hitter
    pull_score = (batter.power - batter.contact) / 100.0
    # Base shift probability from pull tendency (0-40%)
    shift_prob = max(0, pull_score * 0.6) * shift_tendency
    # Power hitters get shifted more
    if batter.power >= 60:
        shift_prob += 0.15 * shift_tendency
    return random.random() < shift_prob


def _apply_shift_modifier(outcome: str, batter: BatterStats) -> str:
    """Modify batted ball outcome when shift is deployed.
    Shift converts ~20% of ground ball singles to outs, but opens gaps
    for doubles on the pull side and allows more opposite-field singles.
    """
    if outcome == "1B":
        # Ground ball singles reduced by shift (20% become outs)
        if random.random() < 0.20:
            return "GO"
        # But some shift-beaters go opposite field for singles (5%)
        # (net: shift still helps, but not free)
    elif outcome == "2B":
        # Shift opens pull-side gaps: 12% of doubles become triples
        if random.random() < 0.12:
            return "3B"
    elif outcome == "GO":
        # Shift occasionally turns routine grounders into hits (3%)
        # when ball finds the hole left by shifted fielders
        if random.random() < 0.03:
            return "1B"

    return outcome


def _should_pinch_hit(lineup: list[BatterStats], current_batter_idx: int,
                     inning: int, score_diff: int,
                     bench: list[BatterStats] = None,
                     opposing_pitcher: PitcherStats = None) -> bool:
    """Check if a batter should be pinch hit for in late innings.

    Considers:
    - Weak batters (overall < 40) in 7th+ inning, close game (within 3 runs)
    - Pitcher spots (power < 35)
    - L/R matchup advantage from available bench bats
    """
    if inning < 7:
        return False
    if not bench:
        return False

    batter = lineup[current_batter_idx % len(lineup)]

    # Close game check (within 3 runs)
    if abs(score_diff) > 3:
        return False

    # Overall rating: average of contact and power
    batter_overall = (batter.contact + batter.power) / 2

    # Pitcher batting (low power rating) - always pinch hit
    if batter.power < 35:
        return True

    # Weak batters (overall < 40)
    if batter_overall < 40:
        # Check if we have someone better on the bench
        best_bench = max(bench, key=lambda b: b.contact + b.power)
        if (best_bench.contact + best_bench.power) > (batter.contact + batter.power):
            return True

    # L/R matchup advantage: if opposing pitcher is same hand as batter,
    # and we have an opposite-hand bench bat with decent ratings
    if opposing_pitcher and batter_overall < 55:
        pitcher_hand = opposing_pitcher.throws
        batter_hand = batter.bats
        # Same-hand disadvantage
        if ((pitcher_hand == "R" and batter_hand == "R") or
                (pitcher_hand == "L" and batter_hand == "L")):
            # Look for opposite-hand bench bat
            for b in bench:
                if ((pitcher_hand == "R" and b.bats in ("L", "S")) or
                        (pitcher_hand == "L" and b.bats in ("R", "S"))):
                    if (b.contact + b.power) >= (batter.contact + batter.power):
                        return True

    return False


def _select_best_pinch_hitter(bench: list[BatterStats],
                               batter: BatterStats,
                               opposing_pitcher: PitcherStats = None) -> BatterStats:
    """Select the best pinch hitter from the bench, considering L/R matchups.

    If the current batter has a same-hand disadvantage vs the pitcher,
    prefer an opposite-hand bench bat. Otherwise pick the strongest overall.
    """
    if not bench:
        return None

    # Check if we should prefer a platoon advantage
    if opposing_pitcher:
        pitcher_hand = opposing_pitcher.throws
        batter_hand = batter.bats
        same_hand = ((pitcher_hand == "R" and batter_hand == "R") or
                     (pitcher_hand == "L" and batter_hand == "L"))
        if same_hand:
            # Filter to opposite-hand bench bats
            platoon_options = [
                b for b in bench
                if ((pitcher_hand == "R" and b.bats in ("L", "S")) or
                    (pitcher_hand == "L" and b.bats in ("R", "S")))
            ]
            if platoon_options:
                return max(platoon_options, key=lambda b: b.contact + b.power)

    # No platoon advantage available or not relevant — pick best overall
    return max(bench, key=lambda b: b.contact + b.power)


def _reposition_after_pinch_hit(lineup: list[BatterStats], ph_slot: int):
    """After a pinch hitter enters, check if they should swap defensive positions.

    If the PH is a poor fielder (fielding < 40) at a demanding position
    (C, SS, 2B, CF), move them to an easier position (LF, RF, 1B, DH)
    by swapping with a lineup player at that easier position.
    """
    ph = lineup[ph_slot]
    DEMANDING_POSITIONS = {"C", "SS", "2B", "CF", "3B"}
    EASY_POSITIONS = {"DH", "LF", "RF", "1B"}

    if ph.position not in DEMANDING_POSITIONS:
        return  # Already at an easy position
    if ph.fielding >= 40:
        return  # Adequate fielder, no swap needed

    # Find a lineup player at an easy position with better fielding
    best_swap = None
    best_swap_idx = None
    for i, b in enumerate(lineup[:9]):
        if i == ph_slot:
            continue
        if b.position in EASY_POSITIONS and b.fielding > ph.fielding:
            if best_swap is None or b.fielding > best_swap.fielding:
                best_swap = b
                best_swap_idx = i

    if best_swap_idx is not None:
        # Swap positions (not lineup slots — they keep their batting order)
        old_ph_pos = ph.position
        ph.position = best_swap.position
        best_swap.position = old_ph_pos


def _should_make_defensive_substitution(lineup: list[BatterStats], inning: int,
                                       score_diff: int, team_ahead: bool,
                                       bench: list[BatterStats] = None) -> tuple:
    """Check if defensive sub should be made in late innings with a lead.

    Returns (lineup_idx, bench_idx) if a sub should be made, or (None, None).
    Replaces poor fielders (fielding < 40) with better defensive bench players.
    Only in 8th-9th inning when team has a lead.
    """
    if not team_ahead or not bench:
        return None, None
    if inning < 8:
        return None, None
    if score_diff < 1:
        return None, None

    # Find poor fielders in the lineup
    poor_fielders = []
    for i, b in enumerate(lineup[:9]):  # only starters
        if b.fielding < 40:
            poor_fielders.append((i, b))

    if not poor_fielders:
        return None, None

    # Find the worst fielder
    worst_idx, worst_batter = min(poor_fielders, key=lambda x: x[1].fielding)

    # Find a bench player with better fielding
    best_defender = None
    best_bench_idx = None
    for j, b in enumerate(bench):
        if b.fielding > worst_batter.fielding:
            if best_defender is None or b.fielding > best_defender.fielding:
                best_defender = b
                best_bench_idx = j

    if best_defender is not None:
        # Higher probability in 9th than 8th
        prob = 0.5 if inning >= 9 else 0.3
        if random.random() < prob:
            return worst_idx, best_bench_idx

    return None, None


def _find_double_switch_candidate(lineup: list[BatterStats], pitcher_batting_idx: int,
                                   current_batter_idx: int) -> int:
    """Find the best lineup slot for a double switch in NL-style (no DH) games.

    When a pitching change happens and the pitcher's spot in the batting order
    is coming up soon (within 2 batters), we want to swap the new pitcher into
    the spot of the weakest hitter who batted most recently, and move that
    hitter's spot to where the pitcher was.

    Args:
        lineup: current batting lineup (9 players)
        pitcher_batting_idx: index in lineup where pitcher currently bats
        current_batter_idx: the global batter index counter (mod len to get position)

    Returns:
        The lineup index of the player to swap with, or -1 if no double switch needed.
    """
    lineup_size = len(lineup)
    if lineup_size < 9:
        return -1

    # Where is the pitcher in the batting order relative to current batter?
    current_slot = current_batter_idx % lineup_size
    pitcher_slot = pitcher_batting_idx % lineup_size

    # Calculate how many batters until pitcher's spot comes up
    distance = (pitcher_slot - current_slot) % lineup_size

    # Only double switch if pitcher's spot is within 2 batters
    if distance > 2:
        return -1

    # Find the weakest hitter who batted most recently (behind the current spot)
    # "Recently batted" = slots just before the current batter in the order
    best_swap_idx = -1
    worst_hitting_score = float('inf')

    for offset in range(1, lineup_size):
        candidate_slot = (current_slot - offset) % lineup_size
        if candidate_slot == pitcher_slot:
            continue  # Skip the pitcher's own slot
        candidate = lineup[candidate_slot]
        hit_score = candidate.contact + candidate.power
        if hit_score < worst_hitting_score:
            worst_hitting_score = hit_score
            best_swap_idx = candidate_slot

    return best_swap_idx


def simulate_game(home_lineup: list[BatterStats], away_lineup: list[BatterStats],
                  home_pitchers: list[PitcherStats], away_pitchers: list[PitcherStats],
                  park: ParkFactors, home_team_id: int = 0, away_team_id: int = 0,
                  home_strategy: dict = None, away_strategy: dict = None,
                  weather: dict = None, game_month: int = None,
                  home_chemistry: int = 50, away_chemistry: int = 50,
                  detailed_log: bool = False, use_dh: bool = True) -> dict:
    """
    Simulate a full baseball game.
    Returns dict with full box score data and play-by-play.

    Args:
        weather: dict with temp, wind_direction, wind_speed, humidity, is_day_game
                If None, will be generated randomly based on game_month
        home_chemistry: home team chemistry score (0-100)
        away_chemistry: away team chemistry score (0-100)
        use_dh: if True (default), use designated hitter. If False, pitcher bats
                and double switches are available during pitching changes.
    """
    from .strategy import (
        DEFAULT_STRATEGY, STEAL_FREQUENCY_MULTIPLIER, BUNT_FREQUENCY_CONFIG,
        HIT_AND_RUN_MULTIPLIER, SQUEEZE_MULTIPLIER
    )

    if home_strategy is None:
        home_strategy = dict(DEFAULT_STRATEGY)
    if away_strategy is None:
        away_strategy = dict(DEFAULT_STRATEGY)

    # Mark home/away batters for home field advantage
    for b in home_lineup:
        b.is_home = True
    for b in away_lineup:
        b.is_home = False

    # Generate or validate weather
    if weather is None:
        weather = _generate_weather(game_month, False)  # is_dome passed separately to weather func

    home_score = 0
    away_score = 0
    innings_home = []
    innings_away = []

    home_batter_idx = 0
    away_batter_idx = 0

    # Play-by-play tracking
    play_by_play = []
    detailed_plays = []  # For live game simulation

    # Pitch log accumulator: list of dicts for pitch_log table
    pitch_log_entries = []
    at_bat_counter = 0  # global at-bat counter for the game

    # Set up pitchers
    home_pitcher_idx = 0
    away_pitcher_idx = 0
    current_home_pitcher = home_pitchers[0]
    current_away_pitcher = away_pitchers[0]
    current_home_pitcher.is_starter = True
    current_away_pitcher.is_starter = True
    current_home_pitcher.pitch_order = 1
    current_away_pitcher.pitch_order = 1

    # Track bench players (players beyond starting 9) and substituted players
    home_bench = list(home_lineup[9:]) if len(home_lineup) > 9 else []
    away_bench = list(away_lineup[9:]) if len(away_lineup) > 9 else []
    # Trim lineups to starting 9 for batting rotation
    home_lineup = home_lineup[:9]
    away_lineup = away_lineup[:9]
    home_substituted = set()  # player_ids permanently removed
    away_substituted = set()  # player_ids permanently removed
    home_removed_players = []  # BatterStats objects removed via substitution
    away_removed_players = []  # BatterStats objects removed via substitution

    # No-DH mode: track which lineup slot the pitcher bats in
    # Default to 9th slot (last in order). Only used when use_dh=False.
    home_pitcher_batting_idx = 8 if not use_dh else -1
    away_pitcher_batting_idx = 8 if not use_dh else -1

    # Helper to create a weak BatterStats for a pitcher in the batting lineup
    def _pitcher_as_batter(pitcher: PitcherStats, batting_order: int) -> BatterStats:
        return BatterStats(
            player_id=pitcher.player_id,
            name=pitcher.name,
            position="P",
            batting_order=batting_order,
            bats="R",  # default
            contact=max(20, pitcher.control // 2),
            power=max(20, pitcher.stuff // 3),
            speed=30,
            clutch=pitcher.clutch,
            fielding=30,
            eye=30,
        )

    # When not using DH, insert pitcher as a weak batter in lineup slot 9
    if not use_dh:
        if len(home_lineup) >= 9:
            home_lineup[8] = _pitcher_as_batter(current_home_pitcher, 9)
        if len(away_lineup) >= 9:
            away_lineup[8] = _pitcher_as_batter(current_away_pitcher, 9)

    def _should_pull_pitcher(p: PitcherStats, inning: int, is_starter: bool,
                             score_diff: int, strategy: dict) -> bool:
        """Decide if pitcher should be replaced.
        Factors in carryover fatigue — fatigued relievers get shorter leashes.
        """
        # HARD CEILING - no pitcher should ever exceed these limits
        STARTER_HARD_CAP = 130   # Absolute max for any starter
        RELIEVER_HARD_CAP = 55   # Absolute max for any reliever

        # Carryover fatigue penalty: reduce pitch limits for fatigued pitchers
        avg_fatigue_mod = (p.fatigue_stuff_modifier + p.fatigue_control_modifier) / 2.0
        fatigue_limit_scale = avg_fatigue_mod  # e.g., 0.85 means 85% of normal limits

        if is_starter:
            if p.pitches >= STARTER_HARD_CAP:
                return True
            stamina_max = 70 + p.stamina * 0.75
            # Per-pitcher custom limit overrides team strategy
            team_limit = strategy.get("pitch_count_limit", 100)
            pitcher_limit = p.custom_pitch_count_limit
            max_pitches = min(pitcher_limit or team_limit, stamina_max)
            max_pitches *= fatigue_limit_scale  # reduce limit if fatigued
            if p.pitches >= max_pitches:
                return True
            max_innings = 5 + (p.stamina - 30) * 0.06
            pitcher_innings = p.ip_outs / 3
            if pitcher_innings >= max_innings:
                return True
            if inning >= 7 and p.runs_allowed >= 4:
                return True
            if p.pitches > 60 and p.er >= 5:
                return True
        else:
            if p.pitches >= RELIEVER_HARD_CAP:
                return True
            max_pitches = 25 + (p.stamina - 30) * 0.4
            max_pitches *= fatigue_limit_scale  # reduce limit if fatigued
            if p.pitches >= max_pitches:
                return True
            # Fatigued relievers: pull after giving up ANY run
            if p.pitched_yesterday and p.er >= 1:
                return True
            if p.er >= 3 and p.pitches >= 20:
                return True
            if p.er >= 2 and p.pitches < 20:
                return False
        return False

    def _select_reliever(pitchers: list, current_idx: int, inning: int,
                         score_diff: int, pitch_order: int,
                         current_batter: BatterStats = None) -> tuple:
        """Select the right reliever based on game situation and bullpen roles.

        Roles: closer, setup, loogy, middle, long
        - Closer: 9th+ inning with lead of 1-3
        - Setup: 7th-8th with lead of 1-3
        - LOOGY: 7th+ inning, close game, facing left-handed batter
        - Long: starter exits before 5th inning
        - Middle: everything else

        Pitchers who pitched yesterday are skipped unless no one else is available.
        """
        # Consider all relievers not just those with higher index (allow reuse)
        # First: fresh pitchers who did NOT pitch yesterday
        available = [(i, p) for i, p in enumerate(pitchers)
                     if i != current_idx and p.pitches == 0 and not p.pitched_yesterday]
        # If no fresh + rested relievers, include those who pitched yesterday but haven't thrown today
        if not available:
            available = [(i, p) for i, p in enumerate(pitchers)
                         if i != current_idx and p.pitches == 0]
        if not available:
            available = [(i, p) for i, p in enumerate(pitchers)
                         if i != current_idx and p.ip_outs < 9]
        if not available:
            # Emergency: everyone is exhausted. Pick whoever has thrown fewest pitches
            emergency = [(i, p) for i, p in enumerate(pitchers) if i != current_idx]
            if emergency:
                pick = min(emergency, key=lambda x: x[1].pitches)
                pick[1].pitch_order = pitch_order
                return pick
            # Truly solo pitcher (only 1 on roster) - they have to keep going
            return current_idx, pitchers[current_idx]

        def _find_by_role(role):
            for idx, p in available:
                if p.role == role:
                    return idx, p
            return None

        # Mop-up guy in blowouts (score diff > 6) - use lowest stuff available
        if abs(score_diff) > 6:
            pick = min(available, key=lambda x: x[1].stuff)
            pick[1].pitch_order = pitch_order
            return pick

        # Closer: 9th+ inning (or extras) with lead of 1-3
        if inning >= 9 and 0 < score_diff <= 3:
            result = _find_by_role("closer")
            if result:
                result[1].pitch_order = pitch_order
                return result

        # Setup man: 7th-8th with lead of 1-3
        if inning in (7, 8) and 0 < score_diff <= 3:
            result = _find_by_role("setup")
            if result:
                result[1].pitch_order = pitch_order
                return result

        # LOOGY: 7th+ inning, close game (within 3 runs), facing LH batter
        if (inning >= 7 and abs(score_diff) <= 3
                and current_batter and current_batter.bats == "L"):
            result = _find_by_role("loogy")
            if result:
                result[1].pitch_order = pitch_order
                return result

        # Long reliever: starter exits before 5th inning
        if inning <= 5:
            result = _find_by_role("long")
            if result:
                result[1].pitch_order = pitch_order
                return result

        # Middle reliever for everything else
        result = _find_by_role("middle")
        if result:
            result[1].pitch_order = pitch_order
            return result

        # Fallback: best available by stuff
        pick = max(available, key=lambda x: x[1].stuff)
        pick[1].pitch_order = pitch_order
        return pick

    # Pre-compute strategy values
    away_steal_mult = STEAL_FREQUENCY_MULTIPLIER.get(
        away_strategy.get("steal_frequency", "normal"), 1.0)
    home_steal_mult = STEAL_FREQUENCY_MULTIPLIER.get(
        home_strategy.get("steal_frequency", "normal"), 1.0)
    away_bunt_rate = BUNT_FREQUENCY_CONFIG.get(
        away_strategy.get("bunt_frequency", "normal"), 0.05)
    home_bunt_rate = BUNT_FREQUENCY_CONFIG.get(
        home_strategy.get("bunt_frequency", "normal"), 0.05)
    away_hit_and_run_mult = HIT_AND_RUN_MULTIPLIER.get(
        away_strategy.get("hit_and_run_freq", "normal"), 1.0)
    home_hit_and_run_mult = HIT_AND_RUN_MULTIPLIER.get(
        home_strategy.get("hit_and_run_freq", "normal"), 1.0)
    away_squeeze_mult = SQUEEZE_MULTIPLIER.get(
        away_strategy.get("squeeze_freq", "conservative"), 0.8)
    home_squeeze_mult = SQUEEZE_MULTIPLIER.get(
        home_strategy.get("squeeze_freq", "conservative"), 0.8)
    away_ibb_threshold = away_strategy.get("ibb_threshold", 80)
    home_ibb_threshold = home_strategy.get("ibb_threshold", 80)
    away_shift_tendency = away_strategy.get("shift_tendency", 0.7)
    home_shift_tendency = home_strategy.get("shift_tendency", 0.7)

    num_innings = 9

    for inning in range(1, num_innings + 10):
        # ============================================================
        # TOP OF INNING (away bats vs home pitcher)
        # ============================================================
        inning_runs = 0
        outs = 0
        bases = BaseState()

        while outs < 3:
            batter = away_lineup[away_batter_idx % len(away_lineup)]

            # Skip substituted players (safety limit to prevent infinite loop)
            _skip_count = 0
            while batter.player_id in away_substituted and _skip_count < 18:
                away_batter_idx += 1
                _skip_count += 1
                batter = away_lineup[away_batter_idx % len(away_lineup)]
            if _skip_count >= 18:
                break  # Safety: all batters substituted (shouldn't happen)

            # Pinch-hit check: replace weak hitters in high-leverage late-inning spots
            available_bench = [b for b in away_bench
                               if b.player_id not in away_substituted]
            if _should_pinch_hit(away_lineup, away_batter_idx, inning,
                                  (away_score + inning_runs) - home_score,
                                  bench=available_bench,
                                  opposing_pitcher=current_home_pitcher):
                if available_bench:
                    ph = _select_best_pinch_hitter(
                        available_bench, batter, current_home_pitcher)
                    # Permanently remove original batter and insert pinch hitter
                    lineup_slot = away_batter_idx % len(away_lineup)
                    away_substituted.add(batter.player_id)
                    away_removed_players.append(batter)
                    ph.batting_order = batter.batting_order
                    ph.position = batter.position
                    away_lineup[lineup_slot] = ph
                    away_bench.remove(ph)
                    # Reposition if PH is a poor fielder at a demanding position
                    _reposition_after_pinch_hit(away_lineup, lineup_slot)
                    if detailed_log:
                        play_by_play.append(
                            f"T{inning}: PH {ph.name} batting for {batter.name}")
                    batter = ph

            # Stolen base attempt
            sb_attempt, sb_success, sb_outs = _attempt_stolen_base(
                bases, outs, away_lineup, current_home_pitcher, away_steal_mult)
            outs += sb_outs
            if outs >= 3:
                break

            # Hit-and-run attempt (runner on 1st, < 2 outs)
            hit_and_run = _attempt_hit_and_run(bases, outs, batter, away_hit_and_run_mult)

            # Suicide squeeze attempt (runner on 3rd, < 2 outs)
            suicide_squeeze = _attempt_suicide_squeeze(bases, outs, batter, away_squeeze_mult)

            # Intentional walk consideration
            next_batter_idx = (away_batter_idx + 1) % len(away_lineup)
            next_batter = away_lineup[next_batter_idx]
            # Skip substituted players when finding the on-deck batter
            _ibb_skip = 0
            while next_batter.player_id in away_substituted and _ibb_skip < 9:
                next_batter_idx = (next_batter_idx + 1) % len(away_lineup)
                next_batter = away_lineup[next_batter_idx]
                _ibb_skip += 1
            intentional_walk = _attempt_intentional_walk(bases, outs, batter, next_batter, away_ibb_threshold)

            # Sac bunt attempt (lower priority than other strategies)
            sac_bunt = (not hit_and_run and not suicide_squeeze and not intentional_walk and
                       _attempt_sac_bunt(batter, bases, outs, away_bunt_rate))

            # Defensive shift deployment
            use_shift = _attempt_defensive_shift(batter, away_shift_tendency)

            if intentional_walk:
                # IBB: advance batter without pitch
                batter.bb += 1
                current_home_pitcher.bb_allowed += 1
                runs = _advance_runners(bases, "BB", batter.player_id, batter.speed, away_lineup)
                inning_runs += runs
                batter.rbi += runs
                current_home_pitcher.runs_allowed += runs
                current_home_pitcher.er += runs
                away_batter_idx += 1
                continue

            if sac_bunt:
                outs += 1
                batter.ab += 1
                if bases.second:
                    bases.third = bases.second
                    bases.second = 0
                if bases.first:
                    bases.second = bases.first
                    bases.first = 0
                away_batter_idx += 1
                continue

            if suicide_squeeze:
                # Squeeze result
                outcome = _apply_suicide_squeeze(batter, current_home_pitcher, park)
                if outcome == "SAC":
                    # Successful squeeze
                    batter.ab += 1
                    outs += 1
                    runs = _advance_runners(bases, "SF", batter.player_id, batter.speed, away_lineup)
                    inning_runs += runs
                    batter.rbi += runs
                    current_home_pitcher.runs_allowed += runs
                    current_home_pitcher.er += runs
                    away_batter_idx += 1
                    continue
                elif outcome == "SO":
                    # Failed squeeze - strikeout
                    batter.ab += 1
                    batter.so += 1
                    current_home_pitcher.so_pitched += 1
                    outs += 1
                    away_batter_idx += 1
                    continue

            leverage = _calculate_leverage(inning, outs, abs(home_score - (away_score + inning_runs)), bases)

            # Resolve at-bat with count
            if hit_and_run:
                # Hit-and-run outcome
                outcome = _apply_hit_and_run(current_home_pitcher, batter, park)
                if outcome in ("GO", "FO", "LD"):
                    # Runner might be out on forced play
                    outs += 1
                    batter.ab += 1
                    _assign_fielding_credit(outcome, home_lineup)
                    # Only ground balls can become double plays (line drives: runners hold)
                    if outcome == "GO" and bases.first and outs < 3:
                        runner_speed = 50
                        for b in away_lineup:
                            if b.player_id == bases.first:
                                runner_speed = b.speed
                                break
                        dp_chance = _calculate_dp_chance(runner_speed, batter.speed)
                        if random.random() < dp_chance:
                            outs += 1
                            bases.first = 0
                else:
                    batter.ab += 1
                    outcome_to_use = _apply_shift_modifier(outcome, batter) if use_shift else outcome
                    if outcome_to_use != outcome:
                        outcome = outcome_to_use

                    if outcome in ("1B", "2B", "3B", "HR"):
                        batter.hits += 1
                        current_home_pitcher.hits_allowed += 1
                        if outcome == "2B":
                            batter.doubles += 1
                        elif outcome == "3B":
                            batter.triples += 1
                        elif outcome == "HR":
                            batter.hr += 1
                            current_home_pitcher.hr_allowed += 1
                    runs = _advance_runners(bases, outcome, batter.player_id, batter.speed, away_lineup)
                    inning_runs += runs
                    batter.rbi += runs
                    current_home_pitcher.runs_allowed += runs
                    current_home_pitcher.er += runs
                away_batter_idx += 1
                continue

            outcome, pitches = _resolve_at_bat_with_count(
                batter, current_home_pitcher, park,
                bases.runners_on(), outs, leverage, weather, home_chemistry)

            # Log pitches for this at-bat
            at_bat_counter += 1
            runners_bitmask = (1 if bases.first else 0) | (2 if bases.second else 0) | (4 if bases.third else 0)
            score_diff = home_score - (away_score + inning_runs)
            for pitch_idx, pitch_detail in enumerate(pitches):
                p_result, p_type, p_velo, p_zone, p_balls, p_strikes = pitch_detail
                pitch_log_entries.append({
                    "inning": inning,
                    "at_bat_num": at_bat_counter,
                    "pitch_num": pitch_idx + 1,
                    "pitcher_id": current_home_pitcher.player_id,
                    "batter_id": batter.player_id,
                    "pitch_type": p_type,
                    "velocity": p_velo,
                    "result": p_result,
                    "zone": p_zone,
                    "count_balls": p_balls,
                    "count_strikes": p_strikes,
                    "outs": outs,
                    "runners_on": runners_bitmask,
                    "score_diff": score_diff,
                })

            # Wild pitch / passed ball check (before outcome processing)
            home_catcher_fielding = next((b.fielding for b in home_lineup[:9] if b.position == "C"), 50)
            if _check_wild_pitch(current_home_pitcher, bases, home_catcher_fielding):
                # Runners advance one base on wild pitch
                wp_runs = _advance_runners(bases, "WP", 0, 50, away_lineup)
                inning_runs += wp_runs
                current_home_pitcher.runs_allowed += wp_runs
                current_home_pitcher.er += wp_runs
            elif _check_passed_ball(home_catcher_fielding, bases):
                pb_runs = _advance_runners(bases, "WP", 0, 50, away_lineup)
                inning_runs += pb_runs
                current_home_pitcher.runs_allowed += pb_runs

            # Apply shift modifier if deployed
            if use_shift and outcome in ("1B", "2B", "3B"):
                outcome = _apply_shift_modifier(outcome, batter)

            if outcome in ("GO", "FO", "LD"):
                # Check for error — use actual fielder position
                if outcome == "GO":
                    fielder_pos = random.choice(["SS", "2B", "3B", "1B"])
                    fielder = next((b for b in home_lineup[:9] if b.position == fielder_pos), None)
                    fielding = fielder.fielding if fielder else 50
                    error_prob = _calculate_error_probability(fielding, is_ground_ball=True,
                                                              position=fielder_pos, batter_speed=batter.speed)
                    if random.random() < error_prob:
                        batter.reached_on_error += 1
                        if fielder:
                            fielder.errors_committed += 1
                        runs = _advance_runners(bases, "E", batter.player_id,
                                              batter.speed, away_lineup)
                        inning_runs += runs
                        batter.rbi += runs
                        current_home_pitcher.runs_allowed += runs
                        current_home_pitcher.er += runs
                        away_batter_idx += 1
                        continue
                elif outcome == "LD":
                    # Line drive errors: ~3% chance, usually infielder
                    fielder_pos = random.choice(["SS", "3B", "2B", "1B", "LF", "CF", "RF"])
                    fielder = next((b for b in home_lineup[:9] if b.position == fielder_pos), None)
                    fielding = fielder.fielding if fielder else 50
                    error_prob = _calculate_error_probability(fielding, is_ground_ball=False,
                                                              position=fielder_pos, batter_speed=batter.speed)
                    if random.random() < error_prob:
                        batter.reached_on_error += 1
                        if fielder:
                            fielder.errors_committed += 1
                        runs = _advance_runners(bases, "E", batter.player_id,
                                              batter.speed, away_lineup)
                        inning_runs += runs
                        batter.rbi += runs
                        current_home_pitcher.runs_allowed += runs
                        current_home_pitcher.er += runs
                        away_batter_idx += 1
                        continue

                # Sac fly conversion: FO with runner on 3rd and < 2 outs
                if outcome == "FO" and bases.third and outs < 2:
                    if random.random() < 0.50:
                        outcome = "SF"
                        outs += 1
                        batter.sf += 1
                        _assign_fielding_credit("SF", home_lineup)
                        runs = _advance_runners(bases, outcome, batter.player_id,
                                                batter.speed, away_lineup)
                        inning_runs += runs
                        batter.rbi += runs
                        current_home_pitcher.runs_allowed += runs
                        current_home_pitcher.er += runs
                        away_batter_idx += 1
                        continue

                outs += 1
                _assign_fielding_credit(outcome, home_lineup)
                # Only ground balls can become double plays (not line drives or fly balls)
                if outcome == "GO" and bases.first and outs < 3:
                    runner_speed = 50
                    for b in away_lineup:
                        if b.player_id == bases.first:
                            runner_speed = b.speed
                            break
                    dp_chance = _calculate_dp_chance(runner_speed, batter.speed)
                    if random.random() < dp_chance:
                        outs += 1
                        bases.first = 0
                        _assign_fielding_credit("GO", home_lineup)  # DP: extra fielding credit

            elif outcome == "SF":
                outs += 1
                batter.sf += 1
                _assign_fielding_credit("SF", home_lineup)
                runs = _advance_runners(bases, outcome, batter.player_id,
                                        batter.speed, away_lineup)
                inning_runs += runs
                batter.rbi += runs
                current_home_pitcher.runs_allowed += runs
                current_home_pitcher.er += runs

            elif outcome == "SO":
                outs += 1
                batter.ab += 1
                batter.so += 1
                current_home_pitcher.so_pitched += 1
                _assign_fielding_credit("SO", home_lineup)

            elif outcome in ("BB", "HBP"):
                if outcome == "BB":
                    batter.bb += 1
                    current_home_pitcher.bb_allowed += 1
                else:
                    batter.hbp += 1
                runs = _advance_runners(bases, outcome, batter.player_id,
                                        batter.speed, away_lineup)
                inning_runs += runs
                batter.rbi += runs
                current_home_pitcher.runs_allowed += runs
                current_home_pitcher.er += runs

            else:
                # Hit
                batter.ab += 1
                batter.hits += 1
                current_home_pitcher.hits_allowed += 1
                if outcome == "2B":
                    batter.doubles += 1
                elif outcome == "3B":
                    batter.triples += 1
                elif outcome == "HR":
                    batter.hr += 1
                    current_home_pitcher.hr_allowed += 1
                runs = _advance_runners(bases, outcome, batter.player_id,
                                        batter.speed, away_lineup)
                inning_runs += runs
                batter.rbi += runs
                current_home_pitcher.runs_allowed += runs
                current_home_pitcher.er += runs

            if outcome not in ("BB", "HBP", "SF"):
                if outcome in ("GO", "FO", "LD"):
                    batter.ab += 1

            away_batter_idx += 1

            score_diff_home = home_score - (away_score + inning_runs)
            if _should_pull_pitcher(current_home_pitcher, inning,
                                    current_home_pitcher.is_starter,
                                    score_diff_home, home_strategy):
                current_home_pitcher.ip_outs += 0
                home_pitcher_idx, current_home_pitcher = _select_reliever(
                    home_pitchers, home_pitcher_idx, inning,
                    score_diff_home, home_pitcher_idx + 2,
                    current_batter=batter)

                # Double switch (NL-style, no DH only)
                if not use_dh and home_pitcher_batting_idx >= 0:
                    swap_idx = _find_double_switch_candidate(
                        home_lineup, home_pitcher_batting_idx, home_batter_idx)
                    if swap_idx >= 0:
                        # Swap: new pitcher takes the weak hitter's batting slot,
                        # weak hitter moves to the old pitcher slot
                        old_pitcher_slot = home_pitcher_batting_idx
                        swapped_player = home_lineup[swap_idx]
                        # Move weak hitter to pitcher's old slot
                        home_lineup[old_pitcher_slot] = swapped_player
                        # Put new pitcher-as-batter in weak hitter's slot
                        home_lineup[swap_idx] = _pitcher_as_batter(
                            current_home_pitcher, swap_idx + 1)
                        home_pitcher_batting_idx = swap_idx
                        if detailed_log:
                            play_by_play.append(
                                f"T{inning}: DOUBLE SWITCH — {current_home_pitcher.name} "
                                f"enters batting {swap_idx + 1}th, "
                                f"{swapped_player.name} moves to {old_pitcher_slot + 1}th")
                    else:
                        # No double switch — just update pitcher in his batting slot
                        home_lineup[home_pitcher_batting_idx] = _pitcher_as_batter(
                            current_home_pitcher, home_pitcher_batting_idx + 1)

        current_home_pitcher.ip_outs += 3
        away_score += inning_runs
        innings_away.append(inning_runs)

        # Defensive substitution check for home team (about to field in bottom half)
        # Home team is on defense during top of inning, but we check between halves
        # Actually: away team just batted; now home team bats. Away team will field.
        # Check away defensive subs (they're about to field the bottom half)
        away_def_bench = [b for b in away_bench if b.player_id not in away_substituted]
        away_score_diff = away_score - home_score
        def_lineup_idx, def_bench_idx = _should_make_defensive_substitution(
            away_lineup, inning, away_score_diff, away_score_diff > 0,
            bench=away_def_bench)
        if def_lineup_idx is not None and def_bench_idx is not None:
            old_player = away_lineup[def_lineup_idx]
            new_player = away_def_bench[def_bench_idx]
            away_substituted.add(old_player.player_id)
            away_removed_players.append(old_player)
            new_player.batting_order = old_player.batting_order
            new_player.position = old_player.position
            away_lineup[def_lineup_idx] = new_player
            away_bench.remove(new_player)
            # Reposition if the defensive sub is poor at the inherited position
            _reposition_after_pinch_hit(away_lineup, def_lineup_idx)
            if detailed_log:
                play_by_play.append(
                    f"T{inning}: DEF SUB {new_player.name} replaces "
                    f"{old_player.name} ({old_player.position})")

        # ============================================================
        # BOTTOM OF INNING (home bats vs away pitcher)
        # ============================================================
        if inning >= 9 and home_score > away_score:
            innings_home.append(None)
            break

        inning_runs = 0
        outs = 0
        bases = BaseState()

        while outs < 3:
            batter = home_lineup[home_batter_idx % len(home_lineup)]

            # Skip substituted players (safety limit to prevent infinite loop)
            _skip_count = 0
            while batter.player_id in home_substituted and _skip_count < 18:
                home_batter_idx += 1
                _skip_count += 1
                batter = home_lineup[home_batter_idx % len(home_lineup)]
            if _skip_count >= 18:
                break  # Safety: all batters substituted (shouldn't happen)

            # Pinch-hit check for home team
            available_bench = [b for b in home_bench
                               if b.player_id not in home_substituted]
            if _should_pinch_hit(home_lineup, home_batter_idx, inning,
                                  home_score + inning_runs - away_score,
                                  bench=available_bench,
                                  opposing_pitcher=current_away_pitcher):
                if available_bench:
                    ph = _select_best_pinch_hitter(
                        available_bench, batter, current_away_pitcher)
                    # Permanently remove original batter and insert pinch hitter
                    lineup_slot = home_batter_idx % len(home_lineup)
                    home_substituted.add(batter.player_id)
                    home_removed_players.append(batter)
                    ph.batting_order = batter.batting_order
                    ph.position = batter.position
                    home_lineup[lineup_slot] = ph
                    home_bench.remove(ph)
                    # Reposition if PH is a poor fielder at a demanding position
                    _reposition_after_pinch_hit(home_lineup, lineup_slot)
                    if detailed_log:
                        play_by_play.append(
                            f"B{inning}: PH {ph.name} batting for {batter.name}")
                    batter = ph

            sb_attempt, sb_success, sb_outs = _attempt_stolen_base(
                bases, outs, home_lineup, current_away_pitcher, home_steal_mult)
            outs += sb_outs
            if outs >= 3:
                break

            # Hit-and-run attempt
            hit_and_run = _attempt_hit_and_run(bases, outs, batter, home_hit_and_run_mult)

            # Suicide squeeze attempt
            suicide_squeeze = _attempt_suicide_squeeze(bases, outs, batter, home_squeeze_mult)

            # Intentional walk consideration
            next_batter_idx = (home_batter_idx + 1) % len(home_lineup)
            next_batter = home_lineup[next_batter_idx]
            # Skip substituted players when finding the on-deck batter
            _ibb_skip = 0
            while next_batter.player_id in home_substituted and _ibb_skip < 9:
                next_batter_idx = (next_batter_idx + 1) % len(home_lineup)
                next_batter = home_lineup[next_batter_idx]
                _ibb_skip += 1
            intentional_walk = _attempt_intentional_walk(bases, outs, batter, next_batter, home_ibb_threshold)

            # Sac bunt attempt
            sac_bunt = (not hit_and_run and not suicide_squeeze and not intentional_walk and
                       _attempt_sac_bunt(batter, bases, outs, home_bunt_rate))

            # Defensive shift deployment
            use_shift = _attempt_defensive_shift(batter, home_shift_tendency)

            if intentional_walk:
                batter.bb += 1
                current_away_pitcher.bb_allowed += 1
                runs = _advance_runners(bases, "BB", batter.player_id, batter.speed, home_lineup)
                inning_runs += runs
                batter.rbi += runs
                current_away_pitcher.runs_allowed += runs
                current_away_pitcher.er += runs
                home_batter_idx += 1
                continue

            if sac_bunt:
                outs += 1
                batter.ab += 1
                if bases.second:
                    bases.third = bases.second
                    bases.second = 0
                if bases.first:
                    bases.second = bases.first
                    bases.first = 0
                home_batter_idx += 1
                continue

            if suicide_squeeze:
                outcome = _apply_suicide_squeeze(batter, current_away_pitcher, park)
                if outcome == "SAC":
                    batter.ab += 1
                    outs += 1
                    runs = _advance_runners(bases, "SF", batter.player_id, batter.speed, home_lineup)
                    inning_runs += runs
                    batter.rbi += runs
                    current_away_pitcher.runs_allowed += runs
                    current_away_pitcher.er += runs
                    home_batter_idx += 1
                    continue
                elif outcome == "SO":
                    batter.ab += 1
                    batter.so += 1
                    current_away_pitcher.so_pitched += 1
                    outs += 1
                    home_batter_idx += 1
                    continue

            leverage = 1.0 + (0.1 * inning if inning >= 7 else 0)
            if abs(away_score - (home_score + inning_runs)) <= 2 and inning >= 7:
                leverage = 1.5

            if hit_and_run:
                outcome = _apply_hit_and_run(current_away_pitcher, batter, park)
                if outcome in ("GO", "FO", "LD"):
                    outs += 1
                    batter.ab += 1
                    _assign_fielding_credit(outcome, away_lineup)
                    if outcome == "GO" and bases.first and outs < 3:
                        runner_speed = 50
                        for b in home_lineup:
                            if b.player_id == bases.first:
                                runner_speed = b.speed
                                break
                        dp_chance = _calculate_dp_chance(runner_speed, batter.speed)
                        if random.random() < dp_chance:
                            outs += 1
                            bases.first = 0
                else:
                    batter.ab += 1
                    outcome_to_use = _apply_shift_modifier(outcome, batter) if use_shift else outcome
                    if outcome_to_use != outcome:
                        outcome = outcome_to_use

                    if outcome in ("1B", "2B", "3B", "HR"):
                        batter.hits += 1
                        current_away_pitcher.hits_allowed += 1
                        if outcome == "2B":
                            batter.doubles += 1
                        elif outcome == "3B":
                            batter.triples += 1
                        elif outcome == "HR":
                            batter.hr += 1
                            current_away_pitcher.hr_allowed += 1
                    runs = _advance_runners(bases, outcome, batter.player_id, batter.speed, home_lineup)
                    inning_runs += runs
                    batter.rbi += runs
                    current_away_pitcher.runs_allowed += runs
                    current_away_pitcher.er += runs
                home_batter_idx += 1
                continue

            outcome, pitches = _resolve_at_bat_with_count(
                batter, current_away_pitcher, park,
                bases.runners_on(), outs, leverage, weather, away_chemistry)

            # Log pitches for this at-bat
            at_bat_counter += 1
            runners_bitmask = (1 if bases.first else 0) | (2 if bases.second else 0) | (4 if bases.third else 0)
            score_diff = away_score - (home_score + inning_runs)
            for pitch_idx, pitch_detail in enumerate(pitches):
                p_result, p_type, p_velo, p_zone, p_balls, p_strikes = pitch_detail
                pitch_log_entries.append({
                    "inning": inning,
                    "at_bat_num": at_bat_counter,
                    "pitch_num": pitch_idx + 1,
                    "pitcher_id": current_away_pitcher.player_id,
                    "batter_id": batter.player_id,
                    "pitch_type": p_type,
                    "velocity": p_velo,
                    "result": p_result,
                    "zone": p_zone,
                    "count_balls": p_balls,
                    "count_strikes": p_strikes,
                    "outs": outs,
                    "runners_on": runners_bitmask,
                    "score_diff": score_diff,
                })

            # Wild pitch / passed ball check
            away_catcher_fielding = next((b.fielding for b in away_lineup[:9] if b.position == "C"), 50)
            if _check_wild_pitch(current_away_pitcher, bases, away_catcher_fielding):
                wp_runs = _advance_runners(bases, "WP", 0, 50, home_lineup)
                inning_runs += wp_runs
                current_away_pitcher.runs_allowed += wp_runs
                current_away_pitcher.er += wp_runs
            elif _check_passed_ball(away_catcher_fielding, bases):
                pb_runs = _advance_runners(bases, "WP", 0, 50, home_lineup)
                inning_runs += pb_runs
                current_away_pitcher.runs_allowed += pb_runs

            # Apply shift modifier if deployed
            if use_shift and outcome in ("1B", "2B", "3B"):
                outcome = _apply_shift_modifier(outcome, batter)

            if outcome in ("GO", "FO", "LD"):
                if outcome == "GO":
                    fielder_pos = random.choice(["SS", "2B", "3B", "1B"])
                    fielder = next((b for b in away_lineup[:9] if b.position == fielder_pos), None)
                    fielding = fielder.fielding if fielder else 50
                    error_prob = _calculate_error_probability(fielding, is_ground_ball=True,
                                                              position=fielder_pos, batter_speed=batter.speed)
                    if random.random() < error_prob:
                        batter.reached_on_error += 1
                        if fielder:
                            fielder.errors_committed += 1
                        runs = _advance_runners(bases, "E", batter.player_id,
                                              batter.speed, home_lineup)
                        inning_runs += runs
                        batter.rbi += runs
                        current_away_pitcher.runs_allowed += runs
                        current_away_pitcher.er += runs
                        home_batter_idx += 1
                        continue
                elif outcome == "LD":
                    fielder_pos = random.choice(["SS", "3B", "2B", "1B", "LF", "CF", "RF"])
                    fielder = next((b for b in away_lineup[:9] if b.position == fielder_pos), None)
                    fielding = fielder.fielding if fielder else 50
                    error_prob = _calculate_error_probability(fielding, is_ground_ball=False,
                                                              position=fielder_pos, batter_speed=batter.speed)
                    if random.random() < error_prob:
                        batter.reached_on_error += 1
                        if fielder:
                            fielder.errors_committed += 1
                        runs = _advance_runners(bases, "E", batter.player_id,
                                              batter.speed, home_lineup)
                        inning_runs += runs
                        batter.rbi += runs
                        current_away_pitcher.runs_allowed += runs
                        current_away_pitcher.er += runs
                        home_batter_idx += 1
                        continue

                # Sac fly conversion: FO with runner on 3rd and < 2 outs
                if outcome == "FO" and bases.third and outs < 2:
                    if random.random() < 0.50:
                        outcome = "SF"
                        outs += 1
                        batter.sf += 1
                        _assign_fielding_credit("SF", away_lineup)
                        runs = _advance_runners(bases, outcome, batter.player_id,
                                                batter.speed, home_lineup)
                        inning_runs += runs
                        batter.rbi += runs
                        current_away_pitcher.runs_allowed += runs
                        current_away_pitcher.er += runs
                        home_batter_idx += 1
                        continue

                outs += 1
                _assign_fielding_credit(outcome, away_lineup)
                if outcome == "GO" and bases.first and outs < 3:
                    runner_speed = 50
                    for b in home_lineup:
                        if b.player_id == bases.first:
                            runner_speed = b.speed
                            break
                    dp_chance = _calculate_dp_chance(runner_speed, batter.speed)
                    if random.random() < dp_chance:
                        outs += 1
                        bases.first = 0
                        _assign_fielding_credit("GO", away_lineup)

            elif outcome == "SF":
                outs += 1
                batter.sf += 1
                _assign_fielding_credit("SF", away_lineup)
                runs = _advance_runners(bases, outcome, batter.player_id,
                                        batter.speed, home_lineup)
                inning_runs += runs
                batter.rbi += runs
                current_away_pitcher.runs_allowed += runs
                current_away_pitcher.er += runs

            elif outcome == "SO":
                outs += 1
                batter.ab += 1
                batter.so += 1
                current_away_pitcher.so_pitched += 1
                _assign_fielding_credit("SO", away_lineup)

            elif outcome in ("BB", "HBP"):
                if outcome == "BB":
                    batter.bb += 1
                    current_away_pitcher.bb_allowed += 1
                else:
                    batter.hbp += 1
                runs = _advance_runners(bases, outcome, batter.player_id,
                                        batter.speed, home_lineup)
                inning_runs += runs
                batter.rbi += runs
                current_away_pitcher.runs_allowed += runs
                current_away_pitcher.er += runs

            else:
                batter.ab += 1
                batter.hits += 1
                current_away_pitcher.hits_allowed += 1
                if outcome == "2B":
                    batter.doubles += 1
                elif outcome == "3B":
                    batter.triples += 1
                elif outcome == "HR":
                    batter.hr += 1
                    current_away_pitcher.hr_allowed += 1
                runs = _advance_runners(bases, outcome, batter.player_id,
                                        batter.speed, home_lineup)
                inning_runs += runs
                batter.rbi += runs
                current_away_pitcher.runs_allowed += runs
                current_away_pitcher.er += runs

            if outcome in ("GO", "FO", "LD"):
                batter.ab += 1

            home_batter_idx += 1

            if inning >= 9 and home_score + inning_runs > away_score:
                current_away_pitcher.ip_outs += outs
                home_score += inning_runs
                innings_home.append(inning_runs)
                num_innings = inning
                break

            score_diff_away = away_score - (home_score + inning_runs)
            if _should_pull_pitcher(current_away_pitcher, inning,
                                    current_away_pitcher.is_starter,
                                    score_diff_away, away_strategy):
                away_pitcher_idx, current_away_pitcher = _select_reliever(
                    away_pitchers, away_pitcher_idx, inning,
                    score_diff_away, away_pitcher_idx + 2,
                    current_batter=batter)

                # Double switch (NL-style, no DH only)
                if not use_dh and away_pitcher_batting_idx >= 0:
                    swap_idx = _find_double_switch_candidate(
                        away_lineup, away_pitcher_batting_idx, away_batter_idx)
                    if swap_idx >= 0:
                        old_pitcher_slot = away_pitcher_batting_idx
                        swapped_player = away_lineup[swap_idx]
                        away_lineup[old_pitcher_slot] = swapped_player
                        away_lineup[swap_idx] = _pitcher_as_batter(
                            current_away_pitcher, swap_idx + 1)
                        away_pitcher_batting_idx = swap_idx
                        if detailed_log:
                            play_by_play.append(
                                f"B{inning}: DOUBLE SWITCH — {current_away_pitcher.name} "
                                f"enters batting {swap_idx + 1}th, "
                                f"{swapped_player.name} moves to {old_pitcher_slot + 1}th")
                    else:
                        away_lineup[away_pitcher_batting_idx] = _pitcher_as_batter(
                            current_away_pitcher, away_pitcher_batting_idx + 1)
        else:
            current_away_pitcher.ip_outs += 3
            home_score += inning_runs
            innings_home.append(inning_runs)

        # Defensive substitution check for home team (about to field next inning's top)
        home_def_bench = [b for b in home_bench if b.player_id not in home_substituted]
        home_score_diff = home_score - away_score
        def_lineup_idx, def_bench_idx = _should_make_defensive_substitution(
            home_lineup, inning, home_score_diff, home_score_diff > 0,
            bench=home_def_bench)
        if def_lineup_idx is not None and def_bench_idx is not None:
            old_player = home_lineup[def_lineup_idx]
            new_player = home_def_bench[def_bench_idx]
            home_substituted.add(old_player.player_id)
            home_removed_players.append(old_player)
            new_player.batting_order = old_player.batting_order
            new_player.position = old_player.position
            home_lineup[def_lineup_idx] = new_player
            home_bench.remove(new_player)
            # Reposition if the defensive sub is poor at the inherited position
            _reposition_after_pinch_hit(home_lineup, def_lineup_idx)
            if detailed_log:
                play_by_play.append(
                    f"B{inning}: DEF SUB {new_player.name} replaces "
                    f"{old_player.name} ({old_player.position})")

        if inning >= 9 and home_score != away_score:
            break

    # Assign pitcher decisions
    _assign_decisions(home_pitchers, away_pitchers, home_score, away_score,
                      innings_home, innings_away)

    # Include substituted-out players in lineups so their stats get saved
    all_home_lineup = home_lineup + home_removed_players
    all_away_lineup = away_lineup + away_removed_players

    # Build bench usage summary for box score display
    home_bench_used = [
        {"player_id": b.player_id, "name": b.name, "position": b.position}
        for b in home_removed_players
    ]
    away_bench_used = [
        {"player_id": b.player_id, "name": b.name, "position": b.position}
        for b in away_removed_players
    ]
    home_bench_remaining = [
        {"player_id": b.player_id, "name": b.name, "position": b.position}
        for b in home_bench
    ]
    away_bench_remaining = [
        {"player_id": b.player_id, "name": b.name, "position": b.position}
        for b in away_bench
    ]

    # Build matchup stats from pitch log entries
    # Group by (batter_id, pitcher_id) and determine at-bat outcomes
    matchup_data = {}  # (batter_id, pitcher_id) -> stats dict
    processed_abs = set()
    for entry in pitch_log_entries:
        ab_key = entry["at_bat_num"]
        bp_key = (entry["batter_id"], entry["pitcher_id"])

        if bp_key not in matchup_data:
            matchup_data[bp_key] = {
                "batter_id": bp_key[0], "pitcher_id": bp_key[1],
                "pa": 0, "ab": 0, "h": 0, "doubles": 0, "triples": 0,
                "hr": 0, "rbi": 0, "bb": 0, "so": 0, "hbp": 0,
            }

        if ab_key not in processed_abs:
            processed_abs.add(ab_key)
            matchup_data[bp_key]["pa"] += 1

    # Enrich matchup data from batter stats (more accurate than pitch log)
    # The pitch log tells us who faced whom; batting lines tell us what happened
    # We'll rely on the pitch log pa count and derive outcomes from batter accumulators
    # This is a reasonable approximation since we track per-at-bat

    # Calculate final WE
    final_we = calculate_win_expectancy(
        max(len(innings_home), len(innings_away)),
        home_score - away_score, 3, 0
    )

    return {
        "home_score": home_score,
        "away_score": away_score,
        "innings_home": innings_home,
        "innings_away": innings_away,
        "home_lineup": all_home_lineup,
        "away_lineup": all_away_lineup,
        "home_pitchers": home_pitchers,
        "away_pitchers": away_pitchers,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "play_by_play": play_by_play,
        "weather": weather,
        "pitch_log": pitch_log_entries,
        "matchup_data": matchup_data,
        "final_win_expectancy": final_we,
        "bench_usage": {
            "home_subbed_out": home_bench_used,
            "away_subbed_out": away_bench_used,
            "home_bench_remaining": home_bench_remaining,
            "away_bench_remaining": away_bench_remaining,
        },
    }


def _assign_decisions(home_pitchers: list, away_pitchers: list,
                      home_score: int, away_score: int,
                      innings_home: list, innings_away: list):
    """Assign W, L, S, H decisions to pitchers.

    Save: finish game with lead of 3 or fewer, pitch at least 1 inning (3 outs)
    Hold: enter in relief with lead, leave with lead, don't finish game
    """
    if home_score == away_score:
        return

    if home_score > away_score:
        winning_pitchers = home_pitchers
        losing_pitchers = away_pitchers
    else:
        winning_pitchers = away_pitchers
        losing_pitchers = home_pitchers

    # Assign Win
    winner = winning_pitchers[0]
    if winner.ip_outs >= 15:
        winner.decision = "W"
    else:
        for p in winning_pitchers[1:]:
            if p.ip_outs > 0:
                winner = p
                break
        winner.decision = "W"

    # Assign Loss
    loser = losing_pitchers[0]
    for p in reversed(losing_pitchers):
        if p.er > 0:
            loser = p
            break
    loser.decision = "L"

    # Assign Save: last pitcher on winning team, finished game, lead <= 3, pitched >= 1 inning
    if len(winning_pitchers) > 1:
        # Find the last pitcher who actually threw
        closer = None
        for p in reversed(winning_pitchers):
            if p.ip_outs > 0:
                closer = p
                break
        if closer and closer.decision != "W":
            margin = abs(home_score - away_score)
            if closer.ip_outs >= 3 and (margin <= 3 or closer.ip_outs >= 9):
                closer.decision = "S"

    # Assign Holds: relief pitchers on winning team who entered with lead,
    # left with lead, and did NOT finish the game (no save)
    if len(winning_pitchers) > 2:
        for p in winning_pitchers[1:]:
            if p.ip_outs > 0 and p.decision is None:
                # Pitched in relief, didn't get W or S, team won
                # A hold means they entered with a lead and maintained it
                # Approximation: if they allowed fewer runs than the margin, they held
                margin = abs(home_score - away_score)
                if p.er <= margin and p.ip_outs >= 1:
                    p.decision = "H"


def _describe_play(batter_name: str, pitcher_name: str, outcome: str,
                   runners_on: str, runs_scored: int, bases: dict = None,
                   is_pitcher_change: bool = False) -> str:
    """Generate natural baseball play-by-play description text."""
    if is_pitcher_change:
        return f"Pitching change: {pitcher_name} takes over"

    descriptions = {
        "1B": [f"{batter_name} singled to left field",
               f"{batter_name} singled to center field",
               f"{batter_name} singled through the hole",
               f"{batter_name} singled to right field"],
        "2B": [f"{batter_name} doubled to left field",
               f"{batter_name} doubled down the line",
               f"{batter_name} doubled to center field"],
        "3B": [f"{batter_name} tripled to the wall",
               f"{batter_name} tripled to right-center"],
        "HR": [f"{batter_name} hit a solo home run to center field",
               f"{batter_name} hit a home run to left field",
               f"{batter_name} hit a home run to right field"],
        "SO": [f"{batter_name} struck out swinging",
               f"{batter_name} struck out looking",
               f"{batter_name} struck out"],
        "BB": [f"{batter_name} walked"],
        "HBP": [f"{batter_name} hit by pitch"],
        "GO": [f"{batter_name} grounded out to short",
               f"{batter_name} grounded out to second",
               f"{batter_name} grounded into a double play"],
        "FO": [f"{batter_name} flied out to left field",
               f"{batter_name} flied out to center field",
               f"{batter_name} flied out to right field"],
        "LD": [f"{batter_name} lined out to shortstop",
               f"{batter_name} lined out to third",
               f"{batter_name} lined out to second",
               f"{batter_name} lined out to center field",
               f"{batter_name} lined out to left field"],
        "SF": [f"{batter_name} hit a sacrifice fly"],
        "E": [f"{batter_name} reached on an error"],
    }

    text = random.choice(descriptions.get(outcome, [f"{batter_name} {outcome}"]))

    if runs_scored > 0:
        if runs_scored == 1:
            text += " (1 run)"
        else:
            text += f" ({runs_scored} runs)"

    if outcome == "HR" and runs_scored > 1:
        text = text.replace("solo home run", f"{runs_scored}-run home run")

    return text
