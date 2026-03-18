"""
Front Office - Manager AI Decision Engine
Personality-driven in-game strategy selection, risk tolerance, learning, and emotional state.
"""
import random
from ..database.db import query, execute


class ManagerAI:
    """AI engine for manager in-game decisions."""

    def __init__(self, team_id: int, db_path: str = None):
        self.team_id = team_id
        self.db_path = db_path
        self._load_manager()
        self._load_emotional_state()

    def _load_manager(self):
        """Load manager personality from coaching_staff table."""
        mgr = query("""
            SELECT * FROM coaching_staff
            WHERE team_id=? AND role='manager' AND is_available=0
            LIMIT 1
        """, (self.team_id,), db_path=self.db_path)

        if mgr:
            m = mgr[0]
            self.name = m.get("name", "Manager")
            self.analytics = m.get("analytics_orientation", 50)
            self.aggressiveness = m.get("aggressiveness", 50)
            self.patience = m.get("patience_with_young_players", 50)
            self.bullpen_mgmt = m.get("bullpen_management", 50)
            self.platoon = m.get("platoon_tendency", 50)
            self.personality = m.get("personality", "steady")
            self.strategy_skill = m.get("game_strategy", 50)
        else:
            # Default manager
            self.name = "Manager"
            self.analytics = 50
            self.aggressiveness = 50
            self.patience = 50
            self.bullpen_mgmt = 50
            self.platoon = 50
            self.personality = "steady"
            self.strategy_skill = 50

    def _load_emotional_state(self):
        """Load emotional state from recent results."""
        recent = query("""
            SELECT home_score, away_score, home_team_id
            FROM schedule
            WHERE (home_team_id=? OR away_team_id=?) AND is_played=1
            ORDER BY game_date DESC LIMIT 10
        """, (self.team_id, self.team_id), db_path=self.db_path) or []

        wins = 0
        for g in recent:
            is_home = g["home_team_id"] == self.team_id
            home_won = (g.get("home_score", 0) or 0) > (g.get("away_score", 0) or 0)
            if (is_home and home_won) or (not is_home and not home_won):
                wins += 1

        self.recent_wins = wins
        self.recent_losses = len(recent) - wins

        # Emotional state
        if wins >= 8:
            self.mood = "confident"
            self.risk_modifier = 1.2  # More willing to take risks
        elif wins >= 6:
            self.mood = "calm"
            self.risk_modifier = 1.0
        elif wins >= 4:
            self.mood = "neutral"
            self.risk_modifier = 1.0
        elif wins >= 2:
            self.mood = "anxious"
            self.risk_modifier = 0.8  # More conservative
        else:
            self.mood = "desperate"
            self.risk_modifier = 1.3  # Desperate = wild swings

    def should_steal(self, runner_speed: int, catcher_arm: int, inning: int,
                     score_diff: int, outs: int) -> bool:
        """Decide whether to attempt a steal."""
        base_chance = (runner_speed - catcher_arm + 50) / 100  # 0-1 range

        # Manager personality adjustments
        aggression_mult = self.aggressiveness / 50  # 0-2 range
        base_chance *= aggression_mult

        # Situational adjustments
        if score_diff > 3:  # Big lead - don't risk it
            base_chance *= 0.3
        elif score_diff < -3:  # Big deficit - more aggressive
            base_chance *= 1.5 if self.mood == "desperate" else 1.2

        if inning >= 7 and abs(score_diff) <= 1:  # Late and close
            base_chance *= 1.3 if self.aggressiveness > 60 else 0.7

        if outs == 2:  # Two outs - less likely
            base_chance *= 0.5

        # Emotional state
        base_chance *= self.risk_modifier

        # Analytics-oriented managers are more selective
        if self.analytics > 70:
            # Only steal if high success probability
            success_prob = max(0, min(1, (runner_speed - 30) / 50))
            if success_prob < 0.7:
                base_chance *= 0.3

        return random.random() < min(0.6, max(0.02, base_chance))

    def should_bunt(self, batter_contact: int, batter_power: int, inning: int,
                    score_diff: int, outs: int, runner_on_first: bool,
                    runner_on_second: bool) -> bool:
        """Decide whether to sacrifice bunt."""
        if outs >= 2:
            return False
        if not runner_on_first and not runner_on_second:
            return False

        base_chance = 0.08

        # Old school managers bunt more
        if self.analytics < 40:
            base_chance *= 2.0
        elif self.analytics > 70:
            base_chance *= 0.3  # Analytics hate bunts

        # Weak hitters bunt more
        if batter_power < 40:
            base_chance *= 2.0
        elif batter_power > 65:
            base_chance *= 0.2  # Don't bunt your power guys

        # Late and close - bunt to move runner
        if inning >= 7 and abs(score_diff) <= 1:
            if self.personality == "disciplinarian":
                base_chance *= 2.5
            elif self.personality == "innovator":
                base_chance *= 0.5

        return random.random() < min(0.3, base_chance)

    def should_hit_and_run(self, batter_contact: int, runner_speed: int,
                           inning: int, outs: int) -> bool:
        """Decide whether to call hit-and-run."""
        if outs >= 2:
            return False

        base_chance = 0.05

        # High contact + fast runner = ideal H&R
        if batter_contact >= 65 and runner_speed >= 60:
            base_chance *= 2.5

        # Aggressive managers love H&R
        base_chance *= (self.aggressiveness / 50)

        # Fiery personality - more H&R
        if self.personality == "fiery":
            base_chance *= 1.5

        # Desperate mood - take chances
        if self.mood == "desperate":
            base_chance *= 1.5

        return random.random() < min(0.2, base_chance)

    def should_intentional_walk(self, batter_power: int, batter_contact: int,
                                 on_deck_power: int, first_base_open: bool,
                                 inning: int, outs: int) -> bool:
        """Decide whether to intentionally walk a batter."""
        if not first_base_open:
            return False

        # Only IBB dangerous hitters
        if batter_power < 65 and batter_contact < 70:
            return False

        # Prefer IBB if next batter is weaker
        if on_deck_power >= batter_power - 5:
            return False  # On-deck is just as dangerous

        base_chance = 0.15

        # Late innings with lead
        if inning >= 7 and outs < 2:
            base_chance *= 2.0

        # Analytics managers are more calculated about IBBs
        if self.analytics > 70:
            power_diff = batter_power - on_deck_power
            if power_diff > 20:
                base_chance *= 2.0
            elif power_diff < 10:
                base_chance *= 0.3

        return random.random() < min(0.5, base_chance)

    def should_pull_starter(self, pitcher_fatigue: float, pitch_count: int,
                            innings_pitched: float, era_today: float,
                            hits_allowed: int, walks_allowed: int,
                            score_diff: int, inning: int) -> bool:
        """Decide whether to pull the starting pitcher."""
        # Hard limits
        if pitch_count >= 120:
            return True
        if pitcher_fatigue >= 0.9:
            return True

        base_pull_chance = 0.0

        # Pitch count thresholds based on bullpen management style
        if self.bullpen_mgmt > 70:
            # Quick hook manager
            if pitch_count >= 80:
                base_pull_chance += 0.3
            if pitch_count >= 90:
                base_pull_chance += 0.4
        elif self.bullpen_mgmt < 30:
            # Let them pitch manager
            if pitch_count >= 100:
                base_pull_chance += 0.2
            if pitch_count >= 110:
                base_pull_chance += 0.4
        else:
            # Normal
            if pitch_count >= 90:
                base_pull_chance += 0.2
            if pitch_count >= 100:
                base_pull_chance += 0.4

        # Getting shelled
        if hits_allowed + walks_allowed >= 8:
            base_pull_chance += 0.5

        # Bad ERA today
        if era_today > 6.0 and innings_pitched >= 3:
            base_pull_chance += 0.3

        # Protect a lead in late innings
        if score_diff > 0 and inning >= 7:
            if self.bullpen_mgmt > 50:
                base_pull_chance += 0.3

        # Emotional state
        if self.mood == "anxious":
            base_pull_chance += 0.1  # Quicker trigger when anxious
        elif self.mood == "confident":
            base_pull_chance -= 0.1  # Trust the starter when confident

        return random.random() < min(0.95, max(0.0, base_pull_chance))

    def should_use_shift(self, batter_power: int, batter_contact: int,
                         batter_speed: int, pull_tendency: float = 0.5) -> bool:
        """Decide whether to employ a defensive shift."""
        if self.analytics < 30:
            return False  # Old school managers don't shift

        # Analytics managers shift more
        base_chance = 0.1

        if self.analytics > 70:
            base_chance = 0.5
        elif self.analytics > 50:
            base_chance = 0.3

        # Shift against power pull hitters
        if batter_power >= 65 and batter_contact < 50:
            base_chance *= 2.0

        # Don't shift against fast guys who can bunt
        if batter_speed >= 70:
            base_chance *= 0.5

        return random.random() < min(0.7, base_chance)

    def choose_pinch_hitter(self, current_batter: dict, bench: list,
                            pitcher_hand: str, inning: int,
                            score_diff: int, outs: int) -> dict:
        """Choose the best pinch hitter from the bench."""
        if not bench or inning < 6:
            return None

        # Only pinch hit in meaningful situations
        if abs(score_diff) > 5:
            return None

        # Don't PH for good hitters
        batter_quality = (current_batter.get("contact_rating", 50) +
                         current_batter.get("power_rating", 50)) / 2
        if batter_quality >= 55:
            return None

        best = None
        best_score = 0

        for ph in bench:
            score = (ph.get("contact_rating", 50) + ph.get("power_rating", 50)) / 2

            # Platoon advantage
            if self.platoon > 50:
                bats = ph.get("bats", "R")
                if pitcher_hand == "L" and bats == "R":
                    score += 5
                elif pitcher_hand == "R" and bats == "L":
                    score += 5

            # Must be meaningfully better
            if score > batter_quality + 8 and score > best_score:
                best = ph
                best_score = score

        return best

    def get_strategy_adjustments(self) -> dict:
        """Get overall strategy adjustments based on manager personality and mood."""
        return {
            "steal_freq": 1.0 + (self.aggressiveness - 50) / 100 * self.risk_modifier,
            "bunt_freq": 1.0 + (50 - self.analytics) / 100,  # Less analytics = more bunts
            "shift_freq": 0.5 + self.analytics / 100,
            "quick_hook": self.bullpen_mgmt / 100,
            "platoon_usage": self.platoon / 100,
            "mood": self.mood,
            "risk_modifier": self.risk_modifier,
        }


def get_manager_ai(team_id: int, db_path: str = None) -> ManagerAI:
    """Factory function to get a ManagerAI for a team."""
    return ManagerAI(team_id, db_path)


def update_manager_learning(team_id: int, game_result: dict, db_path: str = None):
    """After a game, update the manager's learning/adaptation.

    Track what strategies worked and didn't in a simple JSON field.
    """
    # Get strategy used this game
    strategies_used = game_result.get("strategies_used", {})
    won = game_result.get("won", False)

    # Update a simple learning record
    try:
        existing = query("""
            SELECT id FROM coaching_staff
            WHERE team_id=? AND role='manager' AND is_available=0
        """, (team_id,), db_path=db_path)

        if existing and won:
            # Winning reinforces current tendencies slightly
            execute("""
                UPDATE coaching_staff SET career_wins = career_wins + 1
                WHERE team_id=? AND role='manager' AND is_available=0
            """, (team_id,), db_path=db_path)
        elif existing:
            execute("""
                UPDATE coaching_staff SET career_losses = career_losses + 1
                WHERE team_id=? AND role='manager' AND is_available=0
            """, (team_id,), db_path=db_path)
    except Exception:
        pass
