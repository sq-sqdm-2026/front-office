"""
Front Office - Broadcast Rights & Stadium Management
TV broadcast deal negotiation and stadium upgrade system.
"""
import json
from ..database.db import get_connection, query, execute


# Broadcast deal types and their properties
BROADCAST_DEALS = {
    "standard": {
        "name": "Standard Regional",
        "multiplier": 1.0,
        "years": 3,
        "min_value": 35,  # million
        "max_value": 55,
        "fan_loyalty_impact": 0,
        "description": "Standard regional broadcast package"
    },
    "premium_cable": {
        "name": "Premium Cable",
        "multiplier": 1.3,
        "years": 5,
        "min_value": 50,
        "max_value": 80,
        "fan_loyalty_impact": 0,
        "description": "Premium cable exclusive deal - higher revenue, locked 5 years"
    },
    "streaming": {
        "name": "Streaming Exclusive",
        "multiplier": 1.2,
        "years": 4,
        "min_value": 40,
        "max_value": 70,
        "fan_loyalty_impact": -5,
        "description": "Exclusive streaming platform deal - good revenue but reduces fan loyalty"
    },
    "blackout": {
        "name": "Blackout Package",
        "multiplier": 1.5,
        "years": 3,
        "min_value": 60,
        "max_value": 100,
        "fan_loyalty_impact": -10,
        "description": "Aggressive blackout package - high revenue, significant fan loyalty penalty"
    },
}

# Stadium upgrade definitions
STADIUM_UPGRADES = {
    "luxury_suites": {
        "name": "Luxury Suites",
        "cost": 15000000,
        "annual_revenue": 3000000,
        "fan_loyalty_impact": 2,
        "description": "Premium seating with club access"
    },
    "jumbotron": {
        "name": "Jumbotron/Tech",
        "cost": 8000000,
        "annual_revenue": 1500000,
        "fan_loyalty_impact": 5,
        "description": "Modern video displays and stadium tech"
    },
    "concourse": {
        "name": "Concourse Renovation",
        "cost": 12000000,
        "annual_revenue": 2000000,
        "fan_loyalty_impact": 3,
        "description": "Improved concession areas and walkways"
    },
    "field_renovation": {
        "name": "Field Renovation",
        "cost": 5000000,
        "annual_revenue": 500000,
        "fan_loyalty_impact": 2,
        "description": "Improved playing surface and facilities"
    },
    "retractable_roof": {
        "name": "Retractable Roof",
        "cost": 50000000,
        "annual_revenue": 5000000,
        "fan_loyalty_impact": 10,
        "description": "Weather control - no rain delays, enhanced experience"
    },
}


def calculate_broadcast_deal_value(team_id: int, deal_type: str, db_path: str = None) -> int:
    """Calculate annual broadcast deal value based on market size and team performance."""
    team = query("SELECT market_size, fan_base FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if not team:
        return 0

    t = team[0]

    # Base value from market size and fan base
    base_value = (t["market_size"] * 8_000_000) + (t["fan_base"] * 200_000)

    # Get deal multiplier
    deal_info = BROADCAST_DEALS.get(deal_type, BROADCAST_DEALS["standard"])
    multiplier = deal_info["multiplier"]

    # Apply market-specific modifiers
    value = int(base_value * multiplier)

    # Ensure within range for deal type
    min_val = deal_info["min_value"] * 1_000_000
    max_val = deal_info["max_value"] * 1_000_000
    value = max(min_val, min(max_val, value))

    return value


def get_broadcast_status(team_id: int, db_path: str = None) -> dict:
    """Get current broadcast deal status for a team."""
    team = query("SELECT * FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if not team:
        return {}

    t = team[0]

    # Handle legacy broadcast_contract_type (for backward compatibility)
    deal_type = t.get("broadcast_deal_type") or t.get("broadcast_contract_type", "standard")
    if deal_type == "normal":
        deal_type = "standard"
    elif deal_type == "cable":
        deal_type = "premium_cable"

    deal_info = BROADCAST_DEALS.get(deal_type, BROADCAST_DEALS["standard"])
    deal_value = t.get("broadcast_deal_value", 0)

    # Calculate if no value set
    if deal_value == 0:
        deal_value = calculate_broadcast_deal_value(team_id, deal_type, db_path)

    return {
        "team_id": team_id,
        "current_deal_type": deal_type,
        "current_deal_name": deal_info["name"],
        "current_deal_value": deal_value,
        "years_remaining": t.get("broadcast_deal_years_remaining", 3),
        "available_deals": [
            {
                "type": deal_key,
                "name": deal["name"],
                "multiplier": deal["multiplier"],
                "years": deal["years"],
                "min_value": deal["min_value"],
                "max_value": deal["max_value"],
                "fan_loyalty_impact": deal["fan_loyalty_impact"],
                "description": deal["description"],
                "estimated_value": calculate_broadcast_deal_value(team_id, deal_key, db_path)
            }
            for deal_key, deal in BROADCAST_DEALS.items()
        ]
    }


def negotiate_broadcast_deal(team_id: int, deal_type: str, db_path: str = None) -> dict:
    """Negotiate a new broadcast deal."""
    if deal_type not in BROADCAST_DEALS:
        return {"success": False, "error": "Invalid deal type"}

    team = query("SELECT cash FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if not team:
        return {"success": False, "error": "Team not found"}

    deal_info = BROADCAST_DEALS[deal_type]
    new_deal_value = calculate_broadcast_deal_value(team_id, deal_type, db_path)

    # Update team with new broadcast deal
    execute("""
        UPDATE teams SET
            broadcast_deal_type=?,
            broadcast_deal_value=?,
            broadcast_deal_years_remaining=?
        WHERE id=?
    """, (deal_type, new_deal_value, deal_info["years"], team_id), db_path=db_path)

    # Apply fan loyalty impact
    if deal_info["fan_loyalty_impact"] != 0:
        execute("""
            UPDATE teams SET fan_loyalty = MAX(0, MIN(100, fan_loyalty + ?))
            WHERE id=?
        """, (deal_info["fan_loyalty_impact"], team_id), db_path=db_path)

    return {
        "success": True,
        "deal_type": deal_type,
        "deal_name": deal_info["name"],
        "annual_value": new_deal_value,
        "years_locked": deal_info["years"],
        "fan_loyalty_impact": deal_info["fan_loyalty_impact"],
        "message": f"New {deal_info['name']} deal negotiated: ${new_deal_value:,.0f}/year for {deal_info['years']} years"
    }


def get_stadium_status(team_id: int, db_path: str = None) -> dict:
    """Get current stadium status and available upgrades."""
    team = query("SELECT * FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if not team:
        return {}

    t = team[0]

    # Parse purchased upgrades
    purchased_upgrades = {}
    if t.get("stadium_upgrades_json"):
        try:
            purchased_upgrades = json.loads(t["stadium_upgrades_json"])
        except:
            purchased_upgrades = {}

    # Calculate annual revenue from upgrades
    annual_upgrade_revenue = sum(
        STADIUM_UPGRADES[upgrade_key]["annual_revenue"]
        for upgrade_key in purchased_upgrades.keys()
        if upgrade_key in STADIUM_UPGRADES
    )

    return {
        "team_id": team_id,
        "stadium_name": t["stadium_name"],
        "built_year": t.get("stadium_built_year", 2000),
        "capacity": t["stadium_capacity"],
        "condition": t.get("stadium_condition", 85),
        "revenue_boost": t.get("stadium_revenue_boost", 0),
        "annual_upgrade_revenue": annual_upgrade_revenue,
        "purchased_upgrades": list(purchased_upgrades.keys()),
        "available_upgrades": [
            {
                "key": upgrade_key,
                "name": upgrade["name"],
                "cost": upgrade["cost"],
                "annual_revenue": upgrade["annual_revenue"],
                "fan_loyalty_impact": upgrade["fan_loyalty_impact"],
                "description": upgrade["description"],
                "purchased": upgrade_key in purchased_upgrades
            }
            for upgrade_key, upgrade in STADIUM_UPGRADES.items()
        ]
    }


def purchase_stadium_upgrade(team_id: int, upgrade_key: str, db_path: str = None) -> dict:
    """Purchase a stadium upgrade."""
    if upgrade_key not in STADIUM_UPGRADES:
        return {"success": False, "error": "Invalid upgrade"}

    team = query("SELECT cash, stadium_upgrades_json FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if not team:
        return {"success": False, "error": "Team not found"}

    t = team[0]
    upgrade_info = STADIUM_UPGRADES[upgrade_key]
    cost = upgrade_info["cost"]

    # Check if team has enough cash
    if t["cash"] < cost:
        return {"success": False, "error": f"Insufficient funds. Need ${cost:,.0f}, have ${t['cash']:,.0f}"}

    # Check if already purchased
    purchased = {}
    if t.get("stadium_upgrades_json"):
        try:
            purchased = json.loads(t["stadium_upgrades_json"])
        except:
            purchased = {}

    if upgrade_key in purchased:
        return {"success": False, "error": "Upgrade already purchased"}

    # Add to purchased upgrades
    purchased[upgrade_key] = {"purchased_date": "2026-03-16"}

    # Update team
    execute("""
        UPDATE teams SET
            cash = cash - ?,
            stadium_upgrades_json = ?,
            stadium_revenue_boost = stadium_revenue_boost + ?
        WHERE id=?
    """, (cost, json.dumps(purchased), upgrade_info["annual_revenue"], team_id), db_path=db_path)

    # Apply fan loyalty impact
    if upgrade_info["fan_loyalty_impact"] != 0:
        execute("""
            UPDATE teams SET fan_loyalty = MAX(0, MIN(100, fan_loyalty + ?))
            WHERE id=?
        """, (upgrade_info["fan_loyalty_impact"], team_id), db_path=db_path)

    return {
        "success": True,
        "upgrade_key": upgrade_key,
        "upgrade_name": upgrade_info["name"],
        "cost": cost,
        "annual_revenue": upgrade_info["annual_revenue"],
        "fan_loyalty_impact": upgrade_info["fan_loyalty_impact"],
        "message": f"{upgrade_info['name']} purchased for ${cost:,.0f}"
    }


def apply_broadcast_deal_decrement(team_id: int, db_path: str = None):
    """Decrement broadcast deal years and reset if expired."""
    team = query("""
        SELECT broadcast_deal_years_remaining, broadcast_deal_type
        FROM teams WHERE id=?
    """, (team_id,), db_path=db_path)

    if not team:
        return

    t = team[0]
    years_remaining = t.get("broadcast_deal_years_remaining", 3)

    if years_remaining > 0:
        new_years = years_remaining - 1
        execute("""
            UPDATE teams SET broadcast_deal_years_remaining = ?
            WHERE id=?
        """, (new_years, team_id), db_path=db_path)

        # If deal expires, reset to standard
        if new_years == 0:
            default_value = calculate_broadcast_deal_value(team_id, "standard", db_path)
            execute("""
                UPDATE teams SET
                    broadcast_deal_type = 'standard',
                    broadcast_deal_value = ?,
                    broadcast_deal_years_remaining = 3
                WHERE id=?
            """, (default_value, team_id), db_path=db_path)


def apply_broadcast_loyalty_penalties(team_id: int, db_path: str = None):
    """Apply annual fan loyalty penalties for blackout deals."""
    team = query("""
        SELECT broadcast_deal_type FROM teams WHERE id=?
    """, (team_id,), db_path=db_path)

    if not team:
        return

    t = team[0]
    deal_type = t.get("broadcast_deal_type", "standard")

    # Apply penalty if blackout deal
    if deal_type == "blackout":
        execute("""
            UPDATE teams SET fan_loyalty = MAX(0, MIN(100, fan_loyalty - 10))
            WHERE id=?
        """, (team_id,), db_path=db_path)
