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
    """Pitcher effectiveness degrades with pitch count.
    Stamina rating determines when fatigue kicks in.
    Uses a two-phase curve: gradual decline then steep drop-off.
    """
    # Phase 1 threshold: mild fatigue begins
    # Stamina 80 = ~105 pitches, Stamina 30 = ~60 pitches
    mild_threshold = 40 + pitcher.stamina * 0.8  # 64-104 range

    # Phase 2 threshold: severe fatigue (arm is dead)
    # Stamina 80 = ~120 pitches, Stamina 30 = ~75 pitches
    severe_threshold = mild_threshold + 15

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


def _resolve_pitch(batter: BatterStats, pitcher: PitcherStats, count: list,
                  park: ParkFactors, leverage: float = 1.0, weather: dict = None,
                  pitcher_team_chemistry: int = 50) -> str:
    """Resolve a single pitch. Returns: 'ball', 'called_strike', 'swinging_strike', 'foul', 'hbp', 'in_play'"""
    fatigue = _fatigue_modifier(pitcher)
    contact_mod, power_mod = _platoon_adjustment(batter.bats, pitcher.throws, batter.platoon_split_json)

    # Get pitch type
    is_strikeout_sit = count[1] >= 2
    pitch_type = _select_pitch_type(pitcher, count, is_strikeout_sit)
    pitch_mod = _pitch_type_modifier(pitch_type, count[0] > count[1])

    # Home field advantage: slight boost to home batters (~2% contact/power, better eye)
    home_boost = 1.02 if batter.is_home else 1.0

    # Control rating with chemistry modifier determines zone accuracy
    adjusted_control = _apply_chemistry_control_modifier(pitcher.control, pitcher_team_chemistry)
    pitcher_control_mod = _rating_to_prob(int(adjusted_control * fatigue), 1.0)
    pitcher_stuff_mod = _rating_to_prob(int(pitcher.stuff * fatigue), 1.0) * pitch_mod["strikeout"]
    batter_contact_mod = _rating_to_prob(batter.contact, 1.0) * contact_mod * home_boost

    # Eye/plate discipline factor: affects zone recognition and chase rate
    # High eye = better at recognizing balls (more walks, fewer Ks on bad pitches)
    eye_mod = _rating_to_prob(batter.eye, 1.0)  # 0.6-1.4 range

    # Strike zone probability (affected by control and count)
    in_zone_prob = 0.65 * pitcher_control_mod
    if count[1] >= 2:  # two strikes, pitcher ahead
        in_zone_prob = 0.75  # strike zone expands
    elif count[0] >= 2:  # hitter ahead
        in_zone_prob = 0.55  # pitcher avoids zone

    # Decide: ball or pitch in zone
    if random.random() > in_zone_prob:
        return "ball"

    # Pitch in zone: swing or take?
    # High-eye batters are more selective (lower swing rate on marginal pitches)
    # Low-eye batters chase more aggressively
    eye_swing_adj = (50 - batter.eye) * 0.003  # high eye = less swing, low = more swing
    swing_prob = 0.55 + (50 - batter.contact) * 0.005 + count[1] * 0.1 + eye_swing_adj
    swing_prob = max(0.3, min(0.9, swing_prob))

    if random.random() > swing_prob:
        return "called_strike"

    # Batter swings
    # Swinging strike vs contact (eye helps avoid chasing bad pitches that sneak into zone)
    eye_contact_bonus = 1.0 + (batter.eye - 50) * 0.002  # high eye = slightly better contact
    contact_prob = _rating_to_prob(batter.contact, 0.65) * pitch_mod["contact"] * eye_contact_bonus
    contact_prob = max(0.2, min(0.95, contact_prob))

    if random.random() > contact_prob:
        return "swinging_strike"

    # Contact made: foul or in play?
    foul_prob = 0.25
    if count[1] >= 2:
        foul_prob = 0.15  # fewer fouls with 2 strikes

    if random.random() < foul_prob:
        return "foul"

    # Ball in play
    return "in_play"


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

    pitcher_stuff_mod = _rating_to_prob(int(pitcher.stuff * fatigue), 1.0)
    batter_contact_mod = _rating_to_prob(batter.contact * morale_contact_mult, 1.0) * contact_mod * home_boost
    batter_power_mod = _rating_to_prob(batter.power * morale_power_mult, 1.0) * power_mod * home_boost
    batter_speed_mod = _rating_to_prob(batter.speed, 1.0)

    # Base probabilities
    hr_prob = batter_power_mod * 0.033 * park.hr_factor / pitcher_stuff_mod
    double_prob = batter_power_mod * 0.045 * park.double_factor * 0.8 * power_mod
    triple_prob = batter_speed_mod * 0.005 * park.triple_factor * contact_mod
    single_prob = batter_contact_mod * 0.150 * park.hit_factor / pitcher_stuff_mod
    go_prob = 0.22
    fo_prob = 0.22

    # Clutch adjustment: enhanced for high-leverage situations
    if leverage > 1.2:
        # Clutch 70+: +3-5% hit probability
        # Clutch 30-: -3-5% hit probability
        # Clutch 50: neutral
        clutch_bonus = (batter.clutch - 50) * 0.001  # -0.05 to +0.05 range
        hr_prob *= (1.0 + clutch_bonus)
        single_prob *= (1.0 + clutch_bonus)
        double_prob *= (1.0 + clutch_bonus)

    # Normalize
    total = hr_prob + double_prob + triple_prob + single_prob + go_prob + fo_prob
    r = random.random() * total

    cumulative = 0
    for outcome, prob in [
        ("HR", hr_prob), ("3B", triple_prob), ("2B", double_prob),
        ("1B", single_prob), ("GO", go_prob), ("FO", fo_prob)
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
    Returns (outcome, pitches_thrown) where pitches_thrown is a list of pitch results.
    """
    count = [0, 0]  # [balls, strikes]
    pitches_thrown = []

    while True:
        # Resolve this pitch
        result = _resolve_pitch(batter, pitcher, count, park, leverage, weather, pitcher_team_chemistry)
        pitches_thrown.append(result)
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


def _calculate_error_probability(fielding_rating: int, is_ground_ball: bool = True) -> float:
    """Calculate error probability on a batted ball."""
    if is_ground_ball:
        # Ground balls: 2% base rate, adjusted by fielding
        base_rate = 0.02 * (2.0 - fielding_rating / 50)
    else:
        # Fly balls: 0.5% base rate
        base_rate = 0.005 * (2.0 - fielding_rating / 50)

    return max(0.0, min(0.15, base_rate))


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
    elif outcome == "FO":
        # Fly out: outfielder gets putout
        if outfielders:
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

    # Attempt probability: 8% base * (speed / 50) * steal_multiplier
    attempt_prob = 0.08 * (runner.speed / 50.0) * steal_multiplier
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

    pitcher_stuff_mod = _rating_to_prob(int(pitcher.stuff * fatigue), 1.0)
    batter_contact_mod = _rating_to_prob(int(batter.contact * contact_mod_swing), 1.0) * platoon_contact
    batter_power_mod = _rating_to_prob(int(batter.power * power_mod_swing), 1.0) * platoon_power

    # Base probabilities with modifications
    hr_prob = batter_power_mod * 0.02 * park.hr_factor / pitcher_stuff_mod
    double_prob = batter_power_mod * 0.03 * park.double_factor * 0.8 * platoon_power
    triple_prob = 0.001  # Very unlikely on hit-and-run
    single_prob = batter_contact_mod * 0.18 * park.hit_factor / pitcher_stuff_mod
    go_prob = 0.25
    fo_prob = 0.15  # Must swing, can't take strikes

    total = hr_prob + double_prob + triple_prob + single_prob + go_prob + fo_prob
    r = random.random() * total

    cumulative = 0
    for outcome, prob in [
        ("HR", hr_prob), ("3B", triple_prob), ("2B", double_prob),
        ("1B", single_prob), ("GO", go_prob), ("FO", fo_prob)
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
                             ibb_threshold: int = 80) -> bool:
    """Attempt IBB on dangerous hitter when first base open, runner in scoring position."""
    if outs >= 2:
        return False
    if bases.first:
        return False  # First must be open
    if not (bases.second or bases.third):
        return False  # Need runner in scoring position

    if batter.power < ibb_threshold:
        return False

    # If next batter is significantly worse, increase IBB chance
    ibb_prob = 0.3
    if next_batter:
        batter_power = batter.power
        next_power = next_batter.power
        if batter_power - next_power >= 15:
            ibb_prob = 0.7

    return random.random() < ibb_prob


def _attempt_defensive_shift(batter: BatterStats) -> bool:
    """Deploy defensive shift against extreme pull hitters (power > 65, contact < 45)."""
    return batter.power > 65 and batter.contact < 45


def _apply_shift_modifier(outcome: str) -> str:
    """Modify outcome based on shift deployment."""
    if outcome == "1B":
        # Shift reduces singles by 15%, turns some into outs
        if random.random() < 0.15:
            return "GO"
    elif outcome == "2B":
        # Shift increases doubles by 10% (pulled harder)
        if random.random() < 0.10:
            return "2B"  # Likely stays double

    return outcome


def _should_pinch_hit(lineup: list[BatterStats], current_batter_idx: int,
                     inning: int, score_diff: int) -> bool:
    """Check if pitcher should be pinch hit for (late inning, close game)."""
    if inning < 7:
        return False

    batter = lineup[current_batter_idx % len(lineup)]

    # Pitcher batting (low power rating)
    if batter.power < 35:
        # Close game (within 3 runs)
        if abs(score_diff) <= 3:
            return True

    return False


def _should_make_defensive_substitution(lineup: list[BatterStats], inning: int,
                                       score_diff: int, team_ahead: bool) -> bool:
    """Check if defensive sub should be made in late innings with a lead."""
    if not team_ahead:
        return False
    if inning < 7:
        return False
    if score_diff < 1:
        return False

    # Higher probability in late innings
    prob = 0.2 if inning >= 8 else 0.1
    return random.random() < prob


def simulate_game(home_lineup: list[BatterStats], away_lineup: list[BatterStats],
                  home_pitchers: list[PitcherStats], away_pitchers: list[PitcherStats],
                  park: ParkFactors, home_team_id: int = 0, away_team_id: int = 0,
                  home_strategy: dict = None, away_strategy: dict = None,
                  weather: dict = None, game_month: int = None,
                  home_chemistry: int = 50, away_chemistry: int = 50,
                  detailed_log: bool = False) -> dict:
    """
    Simulate a full baseball game.
    Returns dict with full box score data and play-by-play.

    Args:
        weather: dict with temp, wind_direction, wind_speed, humidity, is_day_game
                If None, will be generated randomly based on game_month
        home_chemistry: home team chemistry score (0-100)
        away_chemistry: away team chemistry score (0-100)
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

    # Set up pitchers
    home_pitcher_idx = 0
    away_pitcher_idx = 0
    current_home_pitcher = home_pitchers[0]
    current_away_pitcher = away_pitchers[0]
    current_home_pitcher.is_starter = True
    current_away_pitcher.is_starter = True
    current_home_pitcher.pitch_order = 1
    current_away_pitcher.pitch_order = 1

    def _should_pull_pitcher(p: PitcherStats, inning: int, is_starter: bool,
                             score_diff: int, strategy: dict) -> bool:
        """Decide if pitcher should be replaced."""
        # HARD CEILING - no pitcher should ever exceed these limits
        STARTER_HARD_CAP = 130   # Absolute max for any starter
        RELIEVER_HARD_CAP = 55   # Absolute max for any reliever

        if is_starter:
            if p.pitches >= STARTER_HARD_CAP:
                return True
            stamina_max = 70 + p.stamina * 0.75
            max_pitches = min(strategy.get("pitch_count_limit", 100), stamina_max)
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
            if p.pitches >= max_pitches:
                return True
            if p.er >= 3 and p.pitches >= 20:
                return True
            if p.er >= 2 and p.pitches < 20:
                return False
        return False

    def _select_reliever(pitchers: list, current_idx: int, inning: int,
                         score_diff: int, pitch_order: int) -> tuple:
        """Select the right reliever based on game situation."""
        # Consider all relievers not just those with higher index (allow reuse)
        available = [(i, p) for i, p in enumerate(pitchers)
                     if i != current_idx and p.pitches == 0]
        if not available:
            available = [(i, p) for i, p in enumerate(pitchers)
                         if i != current_idx and p.ip_outs < 9]
        if not available:
            # Emergency: everyone is exhausted. Pick whoever has thrown fewest pitches
            # (excluding current pitcher only if there IS someone else)
            emergency = [(i, p) for i, p in enumerate(pitchers) if i != current_idx]
            if emergency:
                pick = min(emergency, key=lambda x: x[1].pitches)
                pick[1].pitch_order = pitch_order
                return pick
            # Truly solo pitcher (only 1 on roster) - they have to keep going
            return current_idx, pitchers[current_idx]

        closer_idx = len(pitchers) - 1
        setup_idx = len(pitchers) - 2 if len(pitchers) > 2 else closer_idx

        # Mop-up guy in blowouts (score diff > 6)
        if abs(score_diff) > 6:
            pick = min(available, key=lambda x: x[1].stuff)
            pick[1].pitch_order = pitch_order
            return pick

        # Closer only in save situations (9th inning, leading by 1-3)
        if inning >= 9 and 0 < score_diff <= 3:
            for idx, p in available:
                if idx == closer_idx:
                    p.pitch_order = pitch_order
                    return idx, p

        # Setup man in 8th inning
        if inning == 8:
            for idx, p in available:
                if idx == setup_idx:
                    p.pitch_order = pitch_order
                    return idx, p

        # Middle relievers in 6th-7th
        if inning == 7:
            for idx, p in available:
                if idx == setup_idx or idx == setup_idx - 1:
                    p.pitch_order = pitch_order
                    return idx, p

        # Long reliever if starter pulled early (innings 1-5)
        if inning <= 6:
            for idx, p in available:
                p.pitch_order = pitch_order
                return idx, p

        idx, p = available[0]
        p.pitch_order = pitch_order
        return idx, p

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

            # Pinch-hit check: replace weak hitters in high-leverage late-inning spots
            if _should_pinch_hit(away_lineup, away_batter_idx, inning,
                                  (away_score + inning_runs) - home_score):
                # Find best available bench bat (weakest current lineup member replaced)
                bench = [b for b in away_lineup if b.ab == 0 and b.bb == 0 and b.hbp == 0
                         and b.player_id != batter.player_id and b.power > batter.power]
                if bench:
                    ph = max(bench, key=lambda b: b.contact + b.power)
                    batter = ph  # Use pinch hitter for this at-bat

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
            intentional_walk = _attempt_intentional_walk(bases, outs, batter, next_batter, away_ibb_threshold)

            # Sac bunt attempt (lower priority than other strategies)
            sac_bunt = (not hit_and_run and not suicide_squeeze and not intentional_walk and
                       _attempt_sac_bunt(batter, bases, outs, away_bunt_rate))

            # Defensive shift deployment
            use_shift = _attempt_defensive_shift(batter) and random.random() < away_shift_tendency

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

            leverage = 1.0 + (0.1 * inning if inning >= 7 else 0)
            if abs(home_score - (away_score + inning_runs)) <= 2 and inning >= 7:
                leverage = 1.5

            # Resolve at-bat with count
            if hit_and_run:
                # Hit-and-run outcome
                outcome = _apply_hit_and_run(current_home_pitcher, batter, park)
                if outcome in ("GO", "FO"):
                    # Runner might be out on forced play
                    outs += 1
                    batter.ab += 1
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
                    outcome_to_use = _apply_shift_modifier(outcome) if use_shift else outcome
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

            # Apply shift modifier if deployed
            if use_shift and outcome in ("1B", "2B", "3B"):
                outcome = _apply_shift_modifier(outcome)

            if outcome in ("GO", "FO"):
                # Check for error
                fielding = 50  # Default
                if outcome == "GO":
                    # Shortstop/2B fielding
                    error_prob = _calculate_error_probability(fielding, is_ground_ball=True)
                    if random.random() < error_prob:
                        batter.reached_on_error += 1
                        runs = _advance_runners(bases, "E", batter.player_id,
                                              batter.speed, away_lineup)
                        inning_runs += runs
                        batter.rbi += runs
                        current_home_pitcher.runs_allowed += runs
                        current_home_pitcher.er += runs
                        away_batter_idx += 1
                        continue

                outs += 1
                _assign_fielding_credit(outcome, home_lineup)
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
                if outcome in ("GO", "FO"):
                    batter.ab += 1

            away_batter_idx += 1

            score_diff_home = home_score - (away_score + inning_runs)
            if _should_pull_pitcher(current_home_pitcher, inning,
                                    current_home_pitcher.is_starter,
                                    score_diff_home, home_strategy):
                current_home_pitcher.ip_outs += 0
                home_pitcher_idx, current_home_pitcher = _select_reliever(
                    home_pitchers, home_pitcher_idx, inning,
                    score_diff_home, home_pitcher_idx + 2)

        current_home_pitcher.ip_outs += 3
        away_score += inning_runs
        innings_away.append(inning_runs)

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

            # Pinch-hit check for home team
            if _should_pinch_hit(home_lineup, home_batter_idx, inning,
                                  home_score + inning_runs - away_score):
                bench = [b for b in home_lineup if b.ab == 0 and b.bb == 0 and b.hbp == 0
                         and b.player_id != batter.player_id and b.power > batter.power]
                if bench:
                    ph = max(bench, key=lambda b: b.contact + b.power)
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
            intentional_walk = _attempt_intentional_walk(bases, outs, batter, next_batter, home_ibb_threshold)

            # Sac bunt attempt
            sac_bunt = (not hit_and_run and not suicide_squeeze and not intentional_walk and
                       _attempt_sac_bunt(batter, bases, outs, home_bunt_rate))

            # Defensive shift deployment
            use_shift = _attempt_defensive_shift(batter) and random.random() < home_shift_tendency

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
                if outcome in ("GO", "FO"):
                    outs += 1
                    batter.ab += 1
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
                    outcome_to_use = _apply_shift_modifier(outcome) if use_shift else outcome
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

            # Apply shift modifier if deployed
            if use_shift and outcome in ("1B", "2B", "3B"):
                outcome = _apply_shift_modifier(outcome)

            if outcome in ("GO", "FO"):
                fielding = 50
                if outcome == "GO":
                    error_prob = _calculate_error_probability(fielding, is_ground_ball=True)
                    if random.random() < error_prob:
                        batter.reached_on_error += 1
                        runs = _advance_runners(bases, "E", batter.player_id,
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

            if outcome in ("GO", "FO"):
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
                    score_diff_away, away_pitcher_idx + 2)
        else:
            current_away_pitcher.ip_outs += 3
            home_score += inning_runs
            innings_home.append(inning_runs)

        if inning >= 9 and home_score != away_score:
            break

    # Assign pitcher decisions
    _assign_decisions(home_pitchers, away_pitchers, home_score, away_score,
                      innings_home, innings_away)

    return {
        "home_score": home_score,
        "away_score": away_score,
        "innings_home": innings_home,
        "innings_away": innings_away,
        "home_lineup": home_lineup,
        "away_lineup": away_lineup,
        "home_pitchers": home_pitchers,
        "away_pitchers": away_pitchers,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "play_by_play": play_by_play,
        "weather": weather,
    }


def _assign_decisions(home_pitchers: list, away_pitchers: list,
                      home_score: int, away_score: int,
                      innings_home: list, innings_away: list):
    """Assign W, L, S decisions to pitchers."""
    if home_score == away_score:
        return

    if home_score > away_score:
        winning_pitchers = home_pitchers
        losing_pitchers = away_pitchers
    else:
        winning_pitchers = away_pitchers
        losing_pitchers = home_pitchers

    winner = winning_pitchers[0]
    if winner.ip_outs >= 15:
        winner.decision = "W"
    else:
        for p in winning_pitchers[1:]:
            if p.ip_outs > 0:
                winner = p
                break
        winner.decision = "W"

    loser = losing_pitchers[0]
    for p in reversed(losing_pitchers):
        if p.er > 0:
            loser = p
            break
    loser.decision = "L"

    if len(winning_pitchers) > 1:
        closer = winning_pitchers[-1]
        if closer.ip_outs >= 3 and closer.decision != "W":
            margin = abs(home_score - away_score)
            if margin <= 3 or closer.ip_outs >= 9:
                closer.decision = "S"


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
