"""
Front Office - Player Projections
Marcel-style statistical projection system.
Weights past seasons, regresses to league mean, adjusts for age.
"""


def _get_league_averages():
    """Return league average rate stats for regression."""
    return {
        "batting": {
            "avg": 0.248, "obp": 0.315, "slg": 0.400, "ops": 0.715,
            "hr_rate": 0.033, "bb_rate": 0.085, "so_rate": 0.225,
            "sb_rate": 0.03, "2b_rate": 0.045, "3b_rate": 0.005,
        },
        "pitching": {
            "era": 4.20, "whip": 1.28, "k9": 8.5, "bb9": 3.2,
            "hr9": 1.2, "h9": 8.5, "win_pct": 0.500,
        },
    }


def _age_adjustment_batting(age):
    """OPS adjustment per year based on age curve."""
    if age <= 24:
        return 0.010  # still developing
    elif age <= 27:
        return 0.003  # approaching peak
    elif age <= 29:
        return 0.0    # peak
    elif age <= 32:
        return -0.006  # early decline
    elif age <= 35:
        return -0.012  # mid decline
    else:
        return -0.020  # late career


def _age_adjustment_pitching(age):
    """ERA adjustment per year based on age curve."""
    if age <= 24:
        return -0.15  # improving
    elif age <= 28:
        return -0.05  # approaching peak
    elif age <= 30:
        return 0.0    # peak
    elif age <= 33:
        return 0.10   # early decline
    elif age <= 36:
        return 0.20   # mid decline
    else:
        return 0.35   # late career


def _ratings_to_projected_batting(player, pa_estimate=550):
    """For players with no stats, project from ratings."""
    contact = player.get("contact_rating", 50)
    power = player.get("power_rating", 50)
    speed = player.get("speed_rating", 50)
    eye = player.get("eye_rating", 50)

    avg = 0.200 + (contact - 20) * 0.002
    obp = avg + 0.030 + (eye - 20) * 0.001
    slg = avg + 0.050 + (power - 20) * 0.004
    hr = int(pa_estimate * (0.005 + (power - 20) * 0.0008))
    bb = int(pa_estimate * (0.04 + (eye - 20) * 0.0012))
    so = int(pa_estimate * (0.30 - (contact - 20) * 0.002))
    sb = int(pa_estimate * (0.005 + max(0, speed - 50) * 0.001))
    ab = int(pa_estimate * 0.90)
    h = int(ab * avg)
    doubles = int(h * 0.22)
    triples = int(h * 0.03)
    runs = int(pa_estimate * 0.12 + hr * 0.3)
    rbi = int(hr * 2.5 + h * 0.2)
    g = int(pa_estimate / 4.0)

    return {
        "g": g, "pa": pa_estimate, "ab": ab, "r": runs, "h": h,
        "doubles": doubles, "triples": triples, "hr": hr,
        "rbi": rbi, "bb": bb, "so": so, "sb": sb,
        "avg": round(avg, 3), "obp": round(obp, 3),
        "slg": round(slg, 3), "ops": round(obp + slg, 3),
    }


def _ratings_to_projected_pitching(player, is_starter=True):
    """For pitchers with no stats, project from ratings."""
    stuff = player.get("stuff_rating", 50)
    control = player.get("control_rating", 50)
    stamina = player.get("stamina_rating", 50)

    ip = 180.0 if is_starter else 65.0
    era = 5.50 - (stuff - 20) * 0.030 - (control - 20) * 0.020
    whip = 1.60 - (stuff - 20) * 0.006 - (control - 20) * 0.005
    k9 = 5.0 + (stuff - 20) * 0.07
    bb9 = 5.0 - (control - 20) * 0.05

    er = int(era * ip / 9)
    so = int(k9 * ip / 9)
    bb = int(bb9 * ip / 9)
    ha = int(whip * ip - bb)
    hr_a = int(ip * 1.1 / 9)
    gs = int(ip / 6) if is_starter else 0
    g = gs if is_starter else int(ip / 1.0)
    w = int(ip / 9 * 0.55) if is_starter else int(ip / 9 * 0.1)
    l = int(ip / 9 * 0.45) if is_starter else int(ip / 9 * 0.05)
    sv = 0 if is_starter else int(g * 0.3)

    return {
        "g": g, "gs": gs, "w": w, "l": l, "sv": sv,
        "ip": round(ip, 1), "h": ha, "er": er, "bb": bb, "so": so,
        "hr": hr_a, "era": round(era, 2), "whip": round(whip, 2),
        "k9": round(k9, 1), "bb9": round(bb9, 1),
    }


def project_batter(player_id, db):
    """Generate Marcel-style batting projection for a player.

    Weights: current season 5x, last season 4x, 2 seasons ago 3x.
    Regresses to league mean based on PA volume.
    Adjusts for age.
    """
    player = db.execute(
        "SELECT * FROM players WHERE id = ?", (player_id,)
    ).fetchone()
    if not player:
        return None

    player_dict = dict(player)
    age = player_dict["age"]
    position = player_dict["position"]

    # Get past 3 seasons of stats
    stats = db.execute("""
        SELECT season, games, pa, ab, runs, hits, doubles, triples, hr,
               rbi, bb, so, sb, cs, hbp, sf
        FROM batting_stats
        WHERE player_id = ? AND level = 'MLB' AND is_postseason = 0
        ORDER BY season DESC LIMIT 3
    """, (player_id,)).fetchall()

    if not stats:
        # No stats — project from ratings
        return _ratings_to_projected_batting(player_dict)

    # Weight seasons: most recent = 5, previous = 4, oldest = 3
    weights = [5, 4, 3]
    league = _get_league_averages()["batting"]

    total_weight = 0
    weighted_pa = 0
    weighted_ab = 0
    w_h = w_2b = w_3b = w_hr = w_rbi = w_bb = w_so = w_sb = w_r = 0

    for i, s in enumerate(stats):
        s = dict(s)
        w = weights[i] if i < len(weights) else 2
        pa = max(s["pa"], 1)
        ab = max(s["ab"], 1)

        total_weight += w
        weighted_pa += pa * w
        weighted_ab += ab * w
        w_h += s["hits"] * w
        w_2b += s["doubles"] * w
        w_3b += s["triples"] * w
        w_hr += s["hr"] * w
        w_rbi += s["rbi"] * w
        w_bb += s["bb"] * w
        w_so += s["so"] * w
        w_sb += s["sb"] * w
        w_r += s["runs"] * w

    if total_weight == 0:
        return _ratings_to_projected_batting(player_dict)

    avg_pa = weighted_pa / total_weight
    avg_ab = weighted_ab / total_weight

    # Regression amount: fewer PA = more regression to mean
    # At 600 PA, minimal regression. At 100 PA, heavy regression.
    regression_pa = 1200  # PA added at league average for regression
    reg_factor = avg_pa / (avg_pa + regression_pa)

    # Calculate rate stats
    raw_avg = (w_h / total_weight) / max(avg_ab, 1)
    raw_hr_rate = (w_hr / total_weight) / max(avg_pa, 1)
    raw_bb_rate = (w_bb / total_weight) / max(avg_pa, 1)
    raw_so_rate = (w_so / total_weight) / max(avg_pa, 1)
    raw_sb_rate = (w_sb / total_weight) / max(avg_pa, 1)

    # Regress to league mean
    proj_avg = raw_avg * reg_factor + league["avg"] * (1 - reg_factor)
    proj_hr_rate = raw_hr_rate * reg_factor + league["hr_rate"] * (1 - reg_factor)
    proj_bb_rate = raw_bb_rate * reg_factor + league["bb_rate"] * (1 - reg_factor)
    proj_so_rate = raw_so_rate * reg_factor + league["so_rate"] * (1 - reg_factor)
    proj_sb_rate = raw_sb_rate * reg_factor + league["sb_rate"] * (1 - reg_factor)

    # Age adjustment
    age_adj = _age_adjustment_batting(age)
    proj_avg += age_adj * 0.4  # AVG portion of OPS adjustment
    proj_hr_rate += age_adj * 0.003  # Power component

    # Project counting stats for ~600 PA (full season)
    proj_pa = min(680, int(avg_pa * 1.0))
    proj_ab = int(proj_pa * 0.90)
    proj_h = int(proj_ab * max(0.150, min(0.350, proj_avg)))
    proj_hr = int(proj_pa * max(0, proj_hr_rate))
    proj_bb = int(proj_pa * max(0.02, proj_bb_rate))
    proj_so = int(proj_pa * max(0.05, proj_so_rate))
    proj_sb = int(proj_pa * max(0, proj_sb_rate))
    proj_2b = int(proj_h * 0.22)
    proj_3b = int(proj_h * 0.03)
    proj_rbi = int(proj_hr * 2.5 + (proj_h - proj_hr) * 0.20)
    proj_r = int(proj_pa * 0.12 + proj_hr * 0.3)
    proj_g = int(proj_pa / 4.0)

    final_avg = round(proj_h / max(proj_ab, 1), 3)
    obp = round((proj_h + proj_bb) / max(proj_pa, 1), 3)
    slg = round((proj_h + proj_2b + proj_3b * 2 + proj_hr * 3) / max(proj_ab, 1), 3)

    return {
        "g": proj_g, "pa": proj_pa, "ab": proj_ab, "r": proj_r,
        "h": proj_h, "doubles": proj_2b, "triples": proj_3b,
        "hr": proj_hr, "rbi": proj_rbi, "bb": proj_bb,
        "so": proj_so, "sb": proj_sb,
        "avg": final_avg, "obp": obp, "slg": slg,
        "ops": round(obp + slg, 3),
    }


def project_pitcher(player_id, db):
    """Generate Marcel-style pitching projection."""
    player = db.execute(
        "SELECT * FROM players WHERE id = ?", (player_id,)
    ).fetchone()
    if not player:
        return None

    player_dict = dict(player)
    age = player_dict["age"]
    is_sp = player_dict["position"] == "SP"

    stats = db.execute("""
        SELECT season, games, games_started, wins, losses, saves,
               ip_outs, hits_allowed, er, bb, so, hr_allowed, pitches
        FROM pitching_stats
        WHERE player_id = ? AND level = 'MLB' AND is_postseason = 0
        ORDER BY season DESC LIMIT 3
    """, (player_id,)).fetchall()

    if not stats:
        return _ratings_to_projected_pitching(player_dict, is_sp)

    weights = [5, 4, 3]
    league = _get_league_averages()["pitching"]

    total_weight = 0
    w_ip = w_er = w_h = w_bb = w_so = w_hr = w_g = w_gs = w_w = w_l = w_sv = 0

    for i, s in enumerate(stats):
        s = dict(s)
        w = weights[i] if i < len(weights) else 2
        ip_outs = max(s["ip_outs"], 1)

        total_weight += w
        w_ip += ip_outs * w
        w_er += s["er"] * w
        w_h += s["hits_allowed"] * w
        w_bb += s["bb"] * w
        w_so += s["so"] * w
        w_hr += s["hr_allowed"] * w
        w_g += s["games"] * w
        w_gs += s["games_started"] * w
        w_w += s["wins"] * w
        w_l += s["losses"] * w
        w_sv += s["saves"] * w

    if total_weight == 0:
        return _ratings_to_projected_pitching(player_dict, is_sp)

    avg_ip_outs = w_ip / total_weight
    avg_ip = avg_ip_outs / 3.0

    # Regression
    regression_ip = 450  # IP added at league average
    reg_factor = avg_ip / (avg_ip + regression_ip)

    raw_era = (w_er / total_weight) / max(avg_ip, 0.1) * 9
    raw_whip = ((w_h + w_bb) / total_weight) / max(avg_ip, 0.1)
    raw_k9 = (w_so / total_weight) / max(avg_ip, 0.1) * 9
    raw_bb9 = (w_bb / total_weight) / max(avg_ip, 0.1) * 9

    proj_era = raw_era * reg_factor + league["era"] * (1 - reg_factor)
    proj_whip = raw_whip * reg_factor + league["whip"] * (1 - reg_factor)
    proj_k9 = raw_k9 * reg_factor + league["k9"] * (1 - reg_factor)
    proj_bb9 = raw_bb9 * reg_factor + league["bb9"] * (1 - reg_factor)

    # Age adjustment
    age_adj = _age_adjustment_pitching(age)
    proj_era += age_adj

    proj_ip = avg_ip * 1.0
    proj_er = int(proj_era * proj_ip / 9)
    proj_so = int(proj_k9 * proj_ip / 9)
    proj_bb = int(proj_bb9 * proj_ip / 9)
    proj_ha = int(proj_whip * proj_ip - proj_bb)
    proj_hr_a = int(proj_ip * 1.1 / 9)
    proj_g = int(w_g / total_weight)
    proj_gs = int(w_gs / total_weight)
    proj_w = int(w_w / total_weight)
    proj_l = int(w_l / total_weight)
    proj_sv = int(w_sv / total_weight)

    return {
        "g": proj_g, "gs": proj_gs, "w": proj_w, "l": proj_l,
        "sv": proj_sv, "ip": round(proj_ip, 1),
        "h": proj_ha, "er": proj_er, "bb": proj_bb, "so": proj_so,
        "hr": proj_hr_a,
        "era": round(max(0, proj_era), 2),
        "whip": round(max(0, proj_whip), 2),
        "k9": round(max(0, proj_k9), 1),
        "bb9": round(max(0, proj_bb9), 1),
    }
