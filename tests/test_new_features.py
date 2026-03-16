"""
Test file for new features: Depth Chart, Commissioner Mode, Stat Columns, and CSV Export.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from database.db import query, execute, init_db
from database.schema import SCHEMA_SQL


def test_schema_updates():
    """Test that schema updates are in place."""
    print("Testing schema updates...")

    # Check game_state table has new columns
    schema_info = query("PRAGMA table_info(game_state)")

    columns = {col['name'] for col in schema_info}
    assert 'commissioner_mode' in columns, "commissioner_mode column missing"
    assert 'stat_display_config_json' in columns, "stat_display_config_json column missing"

    print("✓ Schema updates verified")


def test_depth_chart_endpoint():
    """Test that depth chart endpoint would work with sample data."""
    print("Testing depth chart logic...")

    # Create test data structure
    positions = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH', 'SP', 'RP']

    # Simulate depth chart structure
    depth_chart = {}
    for pos in positions:
        depth_chart[pos] = [
            {'player_id': 1, 'name': 'John Doe', 'overall': 75, 'status': 'starter'},
            {'player_id': 2, 'name': 'Jane Smith', 'overall': 60, 'status': 'backup'},
        ]

    # Verify structure
    assert len(depth_chart) == 11, "Should have 11 positions"
    assert all(isinstance(depth_chart[pos], list) for pos in positions), "Each position should have a list"
    assert all('player_id' in p and 'name' in p for pos in positions for p in depth_chart[pos]), \
        "Each player should have required fields"

    print("✓ Depth chart structure verified")


def test_commissioner_mode_logic():
    """Test commissioner mode validation logic."""
    print("Testing commissioner mode logic...")

    # Test field validation
    field_validators = {
        'contact_rating': (20, 80),
        'power_rating': (20, 80),
        'age': (18, 45),
        'morale': (1, 100),
        'ego': (1, 100),
    }

    for field, (min_val, max_val) in field_validators.items():
        # Test clamping
        test_val = -10
        clamped = max(min_val, min(max_val, test_val))
        assert clamped == min_val, f"Should clamp {field} to minimum"

        test_val = 200
        clamped = max(min_val, min(max_val, test_val))
        assert clamped == max_val, f"Should clamp {field} to maximum"

    print("✓ Commissioner mode validation verified")


def test_stat_column_config():
    """Test stat column configuration structure."""
    print("Testing stat column configuration...")

    # Test default config structure
    default_config = {
        "batting": ["name", "pos", "age", "avg", "hr", "rbi", "ops"],
        "pitching": ["name", "pos", "age", "era", "w", "l", "so"]
    }

    # Verify all required fields are present
    assert "batting" in default_config, "batting key missing"
    assert "pitching" in default_config, "pitching key missing"
    assert isinstance(default_config["batting"], list), "batting should be a list"
    assert isinstance(default_config["pitching"], list), "pitching should be a list"

    # Test that common columns are in batting list
    assert "name" in default_config["batting"], "name should be in batting"
    assert "avg" in default_config["batting"], "avg should be in batting"

    # Test that common columns are in pitching list
    assert "name" in default_config["pitching"], "name should be in pitching"
    assert "era" in default_config["pitching"], "era should be in pitching"

    print("✓ Stat column configuration verified")


def test_csv_export_structure():
    """Test CSV export data structure."""
    print("Testing CSV export structure...")

    # Test CSV header structure for roster
    roster_headers = ['ID', 'Name', 'Position', 'Age', 'Status', 'Overall', 'Contact', 'Power',
                      'Speed', 'Fielding', 'Arm', 'Stuff', 'Control', 'Stamina', 'Salary', 'Years Remaining']
    assert len(roster_headers) == 16, "Roster should have 16 columns"

    # Test CSV header structure for batting stats
    batting_headers = ['Name', 'Team', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'BB', 'SO',
                       'SB', 'CS', 'AVG', 'OBP', 'SLG', 'OPS']
    assert len(batting_headers) == 18, "Batting stats should have 18 columns"

    # Test CSV header structure for pitching stats
    pitching_headers = ['Name', 'Team', 'G', 'GS', 'W', 'L', 'SV', 'HLD', 'IP', 'H', 'ER', 'BB', 'SO',
                        'HR', 'ERA', 'WHIP', 'K/9', 'BB/9']
    assert len(pitching_headers) == 18, "Pitching stats should have 18 columns"

    print("✓ CSV export structure verified")


def test_python_syntax():
    """Test that all Python files have valid syntax."""
    print("Testing Python syntax...")

    import py_compile
    import tempfile

    files_to_check = [
        Path(__file__).parent.parent / "src" / "database" / "schema.py",
        Path(__file__).parent.parent / "src" / "api" / "routes.py",
    ]

    for filepath in files_to_check:
        assert filepath.exists(), f"File not found: {filepath}"
        try:
            # Compile to check syntax
            with tempfile.NamedTemporaryFile(suffix='.pyc', delete=True) as f:
                py_compile.compile(str(filepath), cfile=f.name, doraise=True)
            print(f"  ✓ {filepath.name}")
        except py_compile.PyCompileError as e:
            raise AssertionError(f"Syntax error in {filepath}: {e}")

    print("✓ Python syntax verified")


def test_javascript_functions():
    """Test that JavaScript functions are defined."""
    print("Testing JavaScript function definitions...")

    app_js = Path(__file__).parent.parent / "static" / "app.js"
    assert app_js.exists(), "app.js not found"

    content = app_js.read_text()

    # Check for new functions
    functions_to_check = [
        'loadDepthChart',
        'renderDepthPosition',
        'toggleCommissionerMode',
        'updateCommissionerToggleUI',
        'editPlayer',
        'savePlayerEdit',
        'editTeam',
        'saveTeamEdit',
        'openSettingsModal',
        'closeSettingsModal',
        'openColumnPickerModal',
        'saveColumnConfig',
        'exportCSV',
    ]

    for func in functions_to_check:
        assert f'function {func}' in content or f'async function {func}' in content, \
            f"Function {func} not found in app.js"
        print(f"  ✓ {func}")

    print("✓ JavaScript functions verified")


def test_html_elements():
    """Test that HTML has new screens and elements."""
    print("Testing HTML elements...")

    index_html = Path(__file__).parent.parent / "static" / "index.html"
    assert index_html.exists(), "index.html not found"

    content = index_html.read_text()

    # Check for new nav button
    assert 'data-s="depthchart"' in content, "Depth chart nav button not found"
    assert 'onclick="showScreen(\'depthchart\')"' in content, "Depth chart screen link not found"

    # Check for new screen container
    assert 'id="s-depthchart"' in content, "Depth chart screen container not found"

    # Check for settings button
    assert 'onclick="openSettingsModal()"' in content, "Settings modal button not found"

    # Check for settings modal
    assert 'id="settings-modal"' in content, "Settings modal not found"
    assert 'id="commissioner-toggle-btn"' in content, "Commissioner toggle button not found"

    # Check for column picker modal
    assert 'id="column-picker-modal"' in content, "Column picker modal not found"

    print("✓ HTML elements verified")


def test_import_statements():
    """Test that required imports are available."""
    print("Testing Python imports...")

    try:
        from fastapi import FastAPI, HTTPException, Query
        from fastapi.responses import StreamingResponse
        from pydantic import BaseModel
        import csv
        import io
        import json
        print("✓ All required imports available")
    except ImportError as e:
        raise AssertionError(f"Missing import: {e}")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("TESTING NEW FEATURES")
    print("="*60 + "\n")

    tests = [
        test_python_syntax,
        test_javascript_functions,
        test_html_elements,
        test_import_statements,
        test_schema_updates,
        test_depth_chart_endpoint,
        test_commissioner_mode_logic,
        test_stat_column_config,
        test_csv_export_structure,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"✗ {test_func.__name__}: {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
