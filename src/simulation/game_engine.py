"""
Front Office - Game Simulation Engine
Math-based game simulator producing realistic box scores from player ratings.

At-bat resolution model based on Baseball Mogul mechanics:
- Player ratings (20-80 scale) map to probability distributions
- Pitcher vs batter matchup with platoon adjustments
- Park factors modify HR/2B/3B rates
- Fatigue degrades pitcher effectiveness
- Clutch ratings affect high-leverage situations
"""
import random
import math
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


def _rating_to_prob(rating: int, baseline: float) -> float:
    """Convert a 20-80 rating to a probability modifier.
    50 = league average = baseline probability.
    Each point above/below 50 shifts probability proportionally.
    """
    # Sigmoid-ish curve centered at 50
    # 20 rating -> ~0.6x baseline, 80 rating -> ~1.5x baseline
    modifier = 1.0 + (rating - 50) * 0.0167
    return baseline * max(0.3, min(2.0, modifier))


def _platoon_adjustment(batter_bats: str, pitcher_throws: str) -> float:
    """Platoon advantage: opposite-hand batters get a boost."""
    if batter_bats == "S":
        return 1.02  # Switch hitters get slight advantage
    if (batter_bats == "L" and pitcher_throws == "R") or \
       (batter_bats == "R" and pitcher_throws == "L"):
        return 1.08  # Opposite hand = advantage
    return 0.92  # Same hand = disadvantage


def _fatigue_modifier(pitcher: PitcherStats) -> float:
    """Pitcher effectiveness degrades with pitch count.
    Stamina rating determines when fatigue kicks in.
    """
    # Stamina 80 = 120+ pitches before major fatigue
    # Stamina 30 = 60 pitches before major fatigue
    fatigue_threshold = 40 + pitcher.stamina * 1.0  # 60-120 range
    if pitcher.pitches < fatigue_threshold:
        return 1.0
    overage = pitcher.pitches - fatigue_threshold
    # Each pitch over threshold degrades by ~1%
    return max(0.6, 1.0 - overage * 0.01)


def _resolve_at_bat(batter: BatterStats, pitcher: PitcherStats,
                    park: ParkFactors, runners_on: int = 0,
                    outs: int = 0, leverage: float = 1.0) -> str:
    """
    Resolve a single plate appearance.
    Returns: 'BB', 'HBP', 'SO', '1B', '2B', '3B', 'HR', 'GO', 'FO', 'SF'
    """
    fatigue = _fatigue_modifier(pitcher)
    platoon = _platoon_adjustment(batter.bats, pitcher.throws)

    # Base probabilities (MLB averages ~2023)
    # BB: .085, HBP: .012, SO: .225, HR: .033, 3B: .005, 2B: .045, 1B: .150, GO: .220, FO: .225
    pitcher_control_mod = _rating_to_prob(int(pitcher.control * fatigue), 1.0)
    pitcher_stuff_mod = _rating_to_prob(int(pitcher.stuff * fatigue), 1.0)
    batter_contact_mod = _rating_to_prob(batter.contact, 1.0) * platoon

    # Walk probability: higher batter eye + lower pitcher control = more walks
    bb_prob = 0.085 * (2.0 - pitcher_control_mod) * park.hit_factor
    hbp_prob = 0.012

    # Strikeout: higher pitcher stuff + lower batter contact = more Ks
    so_prob = 0.225 * pitcher_stuff_mod * (2.0 - batter_contact_mod) * park.so_factor

    # Home run: batter power + park factor
    hr_prob = _rating_to_prob(batter.power, 0.033) * park.hr_factor * platoon / pitcher_stuff_mod

    # Extra base hits
    double_prob = _rating_to_prob(batter.power, 0.045) * park.double_factor * 0.8 * platoon
    triple_prob = _rating_to_prob(batter.speed, 0.005) * park.triple_factor * platoon

    # Single
    single_prob = _rating_to_prob(batter.contact, 0.150) * park.hit_factor * platoon / pitcher_stuff_mod

    # Clutch adjustment for high-leverage situations
    if leverage > 1.2:
        clutch_mod = 1.0 + (batter.clutch - 50) * 0.005
        hr_prob *= clutch_mod
        single_prob *= clutch_mod
        so_prob *= (2.0 - clutch_mod)

    # Sac fly possibility
    sf_prob = 0.015 if runners_on > 0 and outs < 2 else 0.0

    # Ground out vs fly out for remaining probability
    go_prob = 0.22
    fo_prob = 0.22

    # Normalize
    total = bb_prob + hbp_prob + so_prob + hr_prob + double_prob + triple_prob + single_prob + go_prob + fo_prob + sf_prob
    r = random.random() * total

    pitcher.pitches += random.randint(3, 7)  # avg pitches per PA

    cumulative = 0
    for outcome, prob in [
        ("BB", bb_prob), ("HBP", hbp_prob), ("SO", so_prob),
        ("HR", hr_prob), ("3B", triple_prob), ("2B", double_prob),
        ("1B", single_prob), ("SF", sf_prob), ("GO", go_prob), ("FO", fo_prob)
    ]:
        cumulative += prob
        if r < cumulative:
            return outcome

    return "FO"  # fallback


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

    # Credit runs scored to individual batters in the lineup
    if lineup and scorers:
        lineup_by_id = {b.player_id: b for b in lineup}
        for scorer_id in scorers:
            if scorer_id in lineup_by_id:
                lineup_by_id[scorer_id].runs += 1

    return runs


def _calculate_dp_chance(runner_speed: int, batter_speed: int) -> float:
    """Calculate double play probability based on runner and batter speed.
    Base rate ~50%, adjusted by runner speed (fast runners avoid DP)
    and batter speed (slow batters ground into more DP).
    """
    base_rate = 0.50
    # Fast runner (70+) reduces DP chance; slow runner (30-) increases it
    if runner_speed >= 70:
        base_rate = 0.30
    elif runner_speed <= 30:
        base_rate = 0.65
    else:
        # Linear interpolation between 30 and 70
        base_rate = 0.65 - (runner_speed - 30) * (0.35 / 40)

    # Batter speed adjustment: slow batters more likely to GIDP
    batter_mod = 1.0 + (50 - batter_speed) * 0.005  # slow=+boost to DP, fast=-reduction
    base_rate *= max(0.15, min(1.5, batter_mod))

    return max(0.10, min(0.75, base_rate))


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
    # Only low-power/high-speed batters bunt (not cleanup hitters)
    if batter.power >= 60:
        return False
    if random.random() >= bunt_rate:
        return False
    return True


def simulate_game(home_lineup: list[BatterStats], away_lineup: list[BatterStats],
                  home_pitchers: list[PitcherStats], away_pitchers: list[PitcherStats],
                  park: ParkFactors, home_team_id: int = 0, away_team_id: int = 0,
                  home_strategy: dict = None, away_strategy: dict = None) -> dict:
    """
    Simulate a full baseball game.
    Returns dict with full box score data.
    """
    from .strategy import DEFAULT_STRATEGY, STEAL_FREQUENCY_MULTIPLIER, BUNT_FREQUENCY_CONFIG

    if home_strategy is None:
        home_strategy = dict(DEFAULT_STRATEGY)
    if away_strategy is None:
        away_strategy = dict(DEFAULT_STRATEGY)

    home_score = 0
    away_score = 0
    innings_home = []
    innings_away = []

    home_batter_idx = 0
    away_batter_idx = 0

    # Set up pitchers
    home_pitcher_idx = 0
    away_pitcher_idx = 0
    current_home_pitcher = home_pitchers[0]
    current_away_pitcher = away_pitchers[0]
    current_home_pitcher.is_starter = True
    current_away_pitcher.is_starter = True
    current_home_pitcher.pitch_order = 1
    current_away_pitcher.pitch_order = 1

    # Track lead changes for W/L decisions
    home_pitcher_when_lead_taken = None
    away_pitcher_when_lead_taken = None

    def _should_pull_pitcher(p: PitcherStats, inning: int, is_starter: bool,
                             score_diff: int, strategy: dict) -> bool:
        """Decide if pitcher should be replaced."""
        if is_starter:
            # Use strategy pitch count limit or stamina-based calculation
            stamina_max = 70 + p.stamina * 0.75  # 85-130 range
            max_pitches = min(strategy.get("pitch_count_limit", 100), stamina_max)
            if p.pitches >= max_pitches:
                return True
            # Stamina-based inning range: low stamina (30) -> pull after 5,
            # high stamina (80) -> can go 7+
            max_innings = 5 + (p.stamina - 30) * 0.04  # 5.0 to 7.0
            pitcher_innings = p.ip_outs / 3
            if pitcher_innings >= max_innings:
                return True
            if inning >= 7 and p.runs_allowed >= 4:
                return True
            if p.pitches > 60 and p.er >= 5:
                return True
        else:
            # Relievers: usually 1-2 innings max
            max_pitches = 20 + p.stamina * 0.3
            if p.pitches >= max_pitches:
                return True
            if p.er >= 3:
                return True
        return False

    def _select_reliever(pitchers: list, current_idx: int, inning: int,
                         score_diff: int, pitch_order: int) -> tuple:
        """Select the right reliever based on game situation.
        pitchers[0] is the starter, pitchers[1:] are relievers.
        Reliever roles by position in bullpen:
          - Last reliever (highest stuff typically): closer
          - Second to last: setup man
          - Others: middle/long relief
        Returns (new_idx, pitcher).
        """
        available = [(i, p) for i, p in enumerate(pitchers)
                     if i > current_idx and p.pitches == 0]
        if not available:
            # No fresh arms, try anyone not totally spent
            available = [(i, p) for i, p in enumerate(pitchers)
                         if i > current_idx and p.ip_outs < 9]
        if not available:
            return current_idx, pitchers[current_idx]

        num_relievers = len([p for p in pitchers[1:] if True])
        closer_idx = len(pitchers) - 1  # last bullpen arm
        setup_idx = len(pitchers) - 2 if len(pitchers) > 2 else closer_idx

        # Blowout (lead or deficit > 6): use worst available reliever (mop-up)
        if abs(score_diff) > 6:
            # Mop-up: pick the reliever with lowest stuff (first available)
            pick = min(available, key=lambda x: x[1].stuff)
            pick[1].pitch_order = pitch_order
            return pick

        # Inning 9, leading by 1-3: use closer
        if inning >= 9 and 0 < score_diff <= 3:
            for idx, p in available:
                if idx == closer_idx:
                    p.pitch_order = pitch_order
                    return idx, p

        # Inning 8: setup man
        if inning == 8:
            for idx, p in available:
                if idx == setup_idx:
                    p.pitch_order = pitch_order
                    return idx, p

        # Inning 7: next best available
        if inning == 7:
            for idx, p in available:
                if idx == setup_idx or idx == setup_idx - 1:
                    p.pitch_order = pitch_order
                    return idx, p

        # Innings 5-6, losing or close: long reliever (first available reliever)
        if inning <= 6:
            for idx, p in available:
                p.pitch_order = pitch_order
                return idx, p

        # Default: next available
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

    num_innings = 9

    for inning in range(1, num_innings + 10):  # +10 for extras
        # ============================================================
        # TOP OF INNING (away bats vs home pitcher)
        # ============================================================
        inning_runs = 0
        outs = 0
        bases = BaseState()

        while outs < 3:
            batter = away_lineup[away_batter_idx % len(away_lineup)]

            # --- Stolen base attempt before at-bat ---
            sb_attempt, sb_success, sb_outs = _attempt_stolen_base(
                bases, outs, away_lineup, current_home_pitcher, away_steal_mult)
            outs += sb_outs
            if outs >= 3:
                break

            # --- Sacrifice bunt attempt ---
            if _attempt_sac_bunt(batter, bases, outs, away_bunt_rate):
                outs += 1
                batter.ab += 1
                # Advance runners on sac bunt
                if bases.second:
                    bases.third = bases.second
                    bases.second = 0
                if bases.first:
                    bases.second = bases.first
                    bases.first = 0
                away_batter_idx += 1
                continue

            leverage = 1.0 + (0.1 * inning if inning >= 7 else 0)
            if abs(home_score - (away_score + inning_runs)) <= 2 and inning >= 7:
                leverage = 1.5

            outcome = _resolve_at_bat(batter, current_home_pitcher, park,
                                      bases.runners_on(), outs, leverage)

            if outcome in ("GO", "FO"):
                outs += 1
                # Double play chance on GO with runner on first
                if outcome == "GO" and bases.first and outs < 3:
                    # Look up runner speed for DP calculation
                    runner_speed = 50
                    for b in away_lineup:
                        if b.player_id == bases.first:
                            runner_speed = b.speed
                            break
                    dp_chance = _calculate_dp_chance(runner_speed, batter.speed)
                    if random.random() < dp_chance:
                        outs += 1
                        bases.first = 0
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

            # Check pitcher change
            score_diff_home = home_score - (away_score + inning_runs)
            if _should_pull_pitcher(current_home_pitcher, inning,
                                    current_home_pitcher.is_starter,
                                    score_diff_home, home_strategy):
                current_home_pitcher.ip_outs += 0  # partial inning handled below
                home_pitcher_idx, current_home_pitcher = _select_reliever(
                    home_pitchers, home_pitcher_idx, inning,
                    score_diff_home, home_pitcher_idx + 2)

        # Record outs for pitcher
        current_home_pitcher.ip_outs += 3

        away_score += inning_runs
        innings_away.append(inning_runs)

        # ============================================================
        # BOTTOM OF INNING (home bats vs away pitcher)
        # ============================================================
        # Skip bottom 9+ if home team leads
        if inning >= 9 and home_score > away_score:
            innings_home.append(None)  # didn't bat
            break

        inning_runs = 0
        outs = 0
        bases = BaseState()

        while outs < 3:
            batter = home_lineup[home_batter_idx % len(home_lineup)]

            # --- Stolen base attempt before at-bat ---
            sb_attempt, sb_success, sb_outs = _attempt_stolen_base(
                bases, outs, home_lineup, current_away_pitcher, home_steal_mult)
            outs += sb_outs
            if outs >= 3:
                break

            # --- Sacrifice bunt attempt ---
            if _attempt_sac_bunt(batter, bases, outs, home_bunt_rate):
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

            leverage = 1.0 + (0.1 * inning if inning >= 7 else 0)
            if abs(away_score - (home_score + inning_runs)) <= 2 and inning >= 7:
                leverage = 1.5

            outcome = _resolve_at_bat(batter, current_away_pitcher, park,
                                      bases.runners_on(), outs, leverage)

            if outcome in ("GO", "FO"):
                outs += 1
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

            # Walk-off check
            if inning >= 9 and home_score + inning_runs > away_score:
                # Count remaining outs
                current_away_pitcher.ip_outs += outs
                home_score += inning_runs
                innings_home.append(inning_runs)
                # Jump to end
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

        # Check if game is over (9+ innings, not tied)
        if inning >= 9 and home_score != away_score:
            break

    # Assign pitcher decisions
    _assign_decisions(home_pitchers, away_pitchers, home_score, away_score,
                      innings_home, innings_away)

    # Runs scored are now tracked in _advance_runners via lineup -- no zeroing needed

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
    }


def _assign_decisions(home_pitchers: list, away_pitchers: list,
                      home_score: int, away_score: int,
                      innings_home: list, innings_away: list):
    """Assign W, L, S decisions to pitchers."""
    if home_score == away_score:
        return  # tie (shouldn't happen but safety)

    if home_score > away_score:
        # Home team wins
        winning_pitchers = home_pitchers
        losing_pitchers = away_pitchers
    else:
        winning_pitchers = away_pitchers
        losing_pitchers = home_pitchers

    # Winning pitcher: starter if went 5+ IP and team never trailed after,
    # otherwise the reliever on record when lead was taken
    winner = winning_pitchers[0]
    if winner.ip_outs >= 15:  # 5 innings
        winner.decision = "W"
    else:
        # Give W to longest reliever
        for p in winning_pitchers[1:]:
            if p.ip_outs > 0:
                winner = p
                break
        winner.decision = "W"

    # Losing pitcher: starter if gave up the lead, otherwise last reliever who gave up runs
    loser = losing_pitchers[0]
    for p in reversed(losing_pitchers):
        if p.er > 0:
            loser = p
            break
    loser.decision = "L"

    # Save: last pitcher on winning team if entered with lead <= 3 and finished
    if len(winning_pitchers) > 1:
        closer = winning_pitchers[-1]
        if closer.ip_outs >= 3 and closer.decision != "W":
            margin = abs(home_score - away_score)
            if margin <= 3 or closer.ip_outs >= 9:
                closer.decision = "S"
