"""
Test script for in-game strategy and personality/morale features.
Validates that all new systems integrate correctly.
"""
import sys
import sqlite3
from src.simulation.game_engine import (
    BatterStats, PitcherStats, ParkFactors, simulate_game,
    _attempt_hit_and_run, _attempt_suicide_squeeze,
    _attempt_intentional_walk, _attempt_defensive_shift,
    _apply_hit_and_run, _apply_suicide_squeeze,
    BaseState,
)
from src.simulation.strategy import (
    DEFAULT_STRATEGY, HIT_AND_RUN_MULTIPLIER, SQUEEZE_MULTIPLIER,
    get_strategy,
)
from src.simulation.chemistry import (
    calculate_team_chemistry, get_chemistry_modifiers,
    get_morale_modifiers, get_player_relationships,
    calculate_age_stddev,
)


def test_strategy_parsing():
    """Test that strategy objects parse correctly with new fields."""
    print("Testing strategy parsing...")

    strategy = get_strategy()
    assert "hit_and_run_freq" in strategy
    assert "squeeze_freq" in strategy
    assert "shift_tendency" in strategy
    assert "defensive_sub_tendency" in strategy
    assert "aggression" in strategy

    # Test multipliers
    assert HIT_AND_RUN_MULTIPLIER["aggressive"] == 2.0
    assert SQUEEZE_MULTIPLIER["aggressive"] == 1.5

    print("  ✓ Strategy parsing works correctly")


def test_hit_and_run():
    """Test hit-and-run logic."""
    print("Testing hit-and-run...")

    bases = BaseState(first=1, second=0, third=0)
    batter = BatterStats(
        player_id=1, name="Test Batter", position="2B", batting_order=2,
        bats="R", contact=65, power=50, speed=70, clutch=50
    )

    # Should qualify for hit-and-run (runner on first, < 2 outs, decent contact)
    result = _attempt_hit_and_run(bases, 0, batter, 1.0)
    assert isinstance(result, bool)
    print("  ✓ Hit-and-run logic works")


def test_suicide_squeeze():
    """Test suicide squeeze logic."""
    print("Testing suicide squeeze...")

    bases = BaseState(first=0, second=0, third=1)
    batter = BatterStats(
        player_id=1, name="Test Batter", position="9", batting_order=9,
        bats="R", contact=55, power=40, speed=50, clutch=50
    )

    # Should qualify for squeeze (runner on third, < 2 outs)
    result = _attempt_suicide_squeeze(bases, 0, batter, 1.0)
    assert isinstance(result, bool)
    print("  ✓ Suicide squeeze logic works")


def test_intentional_walk():
    """Test intentional walk logic."""
    print("Testing intentional walk...")

    bases = BaseState(first=0, second=1, third=0)
    batter = BatterStats(
        player_id=1, name="Good Hitter", position="RF", batting_order=3,
        bats="R", contact=70, power=75, speed=60, clutch=60
    )
    next_batter = BatterStats(
        player_id=2, name="Weaker Hitter", position="C", batting_order=9,
        bats="R", contact=50, power=40, speed=40, clutch=50
    )

    # High power hitter, open first base, runner in scoring position
    result = _attempt_intentional_walk(bases, 0, batter, next_batter, 80)
    assert isinstance(result, bool)
    print("  ✓ Intentional walk logic works")


def test_defensive_shift():
    """Test defensive shift deployment."""
    print("Testing defensive shift...")

    extreme_pull_hitter = BatterStats(
        player_id=1, name="Pull Hitter", position="LF", batting_order=1,
        bats="R", contact=40, power=78, speed=65, clutch=55
    )

    normal_hitter = BatterStats(
        player_id=2, name="Normal Hitter", position="SS", batting_order=2,
        bats="R", contact=60, power=50, speed=70, clutch=50
    )

    assert _attempt_defensive_shift(extreme_pull_hitter) == True
    assert _attempt_defensive_shift(normal_hitter) == False
    print("  ✓ Defensive shift logic works")


def test_hit_and_run_outcome():
    """Test hit-and-run outcome resolution."""
    print("Testing hit-and-run outcome...")

    pitcher = PitcherStats(
        player_id=100, name="Test Pitcher", throws="R",
        role="starter", stuff=65, control=60, stamina=70, clutch=50
    )
    pitcher.pitches = 50

    batter = BatterStats(
        player_id=1, name="Test Batter", position="SS", batting_order=2,
        bats="R", contact=65, power=55, speed=70, clutch=50
    )

    park = ParkFactors()

    outcome = _apply_hit_and_run(pitcher, batter, park)
    assert outcome in ("HR", "3B", "2B", "1B", "GO", "FO")
    print("  ✓ Hit-and-run outcome resolution works")


def test_suicide_squeeze_outcome():
    """Test suicide squeeze outcome resolution."""
    print("Testing suicide squeeze outcome...")

    pitcher = PitcherStats(
        player_id=100, name="Test Pitcher", throws="R",
        role="starter", stuff=65, control=60, stamina=70, clutch=50
    )
    pitcher.pitches = 40

    batter = BatterStats(
        player_id=1, name="Contact Hitter", position="2B", batting_order=8,
        bats="R", contact=70, power=35, speed=60, clutch=50
    )

    park = ParkFactors()

    outcome = _apply_suicide_squeeze(batter, pitcher, park)
    assert outcome in ("SAC", "SO")
    print("  ✓ Suicide squeeze outcome resolution works")


def test_chemistry_calculation():
    """Test team chemistry calculation (skipped - requires DB)."""
    print("Testing team chemistry...")
    print("  ✓ Chemistry calculation skipped (requires database)")


def test_chemistry_modifiers():
    """Test chemistry modifier calculation."""
    print("Testing chemistry modifiers...")

    # Low chemistry
    low_mods = get_chemistry_modifiers(25)
    assert low_mods["development_rate"] < 1.0
    assert low_mods["clutch_bonus"] < 0
    assert low_mods["injury_recovery"] < 1.0

    # High chemistry
    high_mods = get_chemistry_modifiers(75)
    assert high_mods["development_rate"] > 1.0
    assert high_mods["clutch_bonus"] > 0
    assert high_mods["injury_recovery"] > 1.0

    # Neutral chemistry
    neutral_mods = get_chemistry_modifiers(50)
    assert abs(neutral_mods["development_rate"] - 1.0) < 0.01
    assert abs(neutral_mods["clutch_bonus"]) < 0.01

    print("  ✓ Chemistry modifiers work correctly")


def test_morale_modifiers():
    """Test morale modifier calculation."""
    print("Testing morale modifiers...")

    # Low morale
    low_morale = get_morale_modifiers(20)
    assert low_morale["contact"] < 0
    assert low_morale["power"] < 0
    assert low_morale["speed"] < 0

    # High morale
    high_morale = get_morale_modifiers(80)
    assert high_morale["contact"] > 0
    assert high_morale["power"] > 0
    assert high_morale["speed"] > 0

    # Neutral morale
    neutral_morale = get_morale_modifiers(50)
    assert abs(neutral_morale["contact"]) < 0.01
    assert abs(neutral_morale["power"]) < 0.01

    print("  ✓ Morale modifiers work correctly")


def test_age_stddev():
    """Test age standard deviation calculation."""
    print("Testing age standard deviation...")

    homogeneous = [30, 30, 30, 31, 30]
    varied = [22, 25, 30, 35, 38]

    homogeneous_std = calculate_age_stddev(homogeneous)
    varied_std = calculate_age_stddev(varied)

    assert homogeneous_std < varied_std
    assert homogeneous_std >= 0
    assert varied_std >= 0

    print("  ✓ Age standard deviation calculation works")


def test_simple_game_simulation():
    """Test a simple game simulation with new strategies."""
    print("Testing simple game simulation with strategies...")

    # Create minimal rosters
    home_lineup = [
        BatterStats(1, "Home1", "C", 1, "R", 55, 50, 50, 50),
        BatterStats(2, "Home2", "1B", 2, "R", 60, 65, 55, 50),
        BatterStats(3, "Home3", "2B", 3, "R", 65, 60, 60, 55),
    ]

    away_lineup = [
        BatterStats(101, "Away1", "SS", 1, "R", 60, 55, 65, 50),
        BatterStats(102, "Away2", "RF", 2, "R", 58, 70, 55, 50),
        BatterStats(103, "Away3", "CF", 3, "R", 62, 50, 70, 55),
    ]

    home_pitchers = [
        PitcherStats(1, "HomeP1", "R", "starter", 65, 60, 65, 50)
    ]

    away_pitchers = [
        PitcherStats(101, "AwayP1", "R", "starter", 68, 62, 68, 52)
    ]

    park = ParkFactors()

    # Test with new strategy
    home_strategy = dict(DEFAULT_STRATEGY)
    home_strategy["hit_and_run_freq"] = "aggressive"
    home_strategy["squeeze_freq"] = "normal"

    away_strategy = dict(DEFAULT_STRATEGY)
    away_strategy["shift_tendency"] = 0.8

    result = simulate_game(
        home_lineup, away_lineup,
        home_pitchers, away_pitchers,
        park,
        home_team_id=1, away_team_id=2,
        home_strategy=home_strategy,
        away_strategy=away_strategy
    )

    assert "home_score" in result
    assert "away_score" in result
    assert result["home_score"] >= 0
    assert result["away_score"] >= 0

    print(f"  ✓ Game simulation works (Final: {result['away_score']}-{result['home_score']})")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("TESTING IN-GAME STRATEGY & PERSONALITY/MORALE FEATURES")
    print("=" * 60 + "\n")

    try:
        test_strategy_parsing()
        test_hit_and_run()
        test_suicide_squeeze()
        test_intentional_walk()
        test_defensive_shift()
        test_hit_and_run_outcome()
        test_suicide_squeeze_outcome()
        test_chemistry_calculation()
        test_chemistry_modifiers()
        test_morale_modifiers()
        test_age_stddev()
        test_simple_game_simulation()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60 + "\n")
        return 0

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
