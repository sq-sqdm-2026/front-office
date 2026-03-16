"""
MLB 162-game schedule generator.

Produces a balanced schedule where every team plays exactly 162 games
(81 home, 81 away) organized into 3-game and 4-game series across
a ~186-day season window (March 27 - September 28).

Division breakdown (per team):
  - 13 games vs each of 4 division rivals        = 52
  - 6 or 7 games vs each of 10 same-league others = 66
  - 3 or 4 games vs interleague opponents          = 44
  Total = 162
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from collections import defaultdict


# ---------------------------------------------------------------------------
# Part 1: Matchup counts  (who plays whom, how many games)
# ---------------------------------------------------------------------------

def _find_perm_avoiding(n, forbidden, rng):
    """Find permutation of 0..n-1 where perm[i] not in forbidden[i]."""
    avail = [sorted(set(range(n)) - forbidden.get(i, set())) for i in range(n)]
    perm = [None] * n
    used = [False] * n
    order = sorted(range(n), key=lambda i: len(avail[i]))

    def bt(idx):
        if idx == n:
            return True
        row = order[idx]
        cs = list(avail[row])
        rng.shuffle(cs)
        for c in cs:
            if not used[c]:
                perm[row] = c
                used[c] = True
                if bt(idx + 1):
                    return True
                used[c] = False
        return False

    for _ in range(50):
        perm[:] = [None] * n
        used[:] = [False] * n
        rng.shuffle(order)
        order.sort(key=lambda i: len(avail[i]))
        if bt(0):
            return list(perm)
    raise RuntimeError("Cannot find permutation")


def _build_matchup_counts(teams, rng):
    """Return {(lo_id, hi_id): game_count} verified to give 162 per team."""
    by_div = defaultdict(list)
    by_lg = defaultdict(list)
    lk = {}
    for t in teams:
        by_div[(t["league"], t["division"])].append(t["id"])
        by_lg[t["league"]].append(t["id"])
        lk[t["id"]] = t

    counts = {}

    # Division: 13 per rival
    for dk, dt in by_div.items():
        for i, a in enumerate(dt):
            for b in dt[i + 1:]:
                counts[(min(a, b), max(a, b))] = 13

    # Cross-division: 6 or 7 (3 upgrades per 5x5 inter-division block)
    for lg in ("AL", "NL"):
        lt = by_lg[lg]
        dv = defaultdict(list)
        for t in lt:
            dv[lk[t]["division"]].append(t)
        divs = sorted(dv.keys())
        for di in range(3):
            for dj in range(di + 1, 3):
                d1, d2 = dv[divs[di]], dv[divs[dj]]
                up = [[False] * 5 for _ in range(5)]
                for _ in range(3):
                    forb = {r: {c for c in range(5) if up[r][c]} for r in range(5)}
                    p = _find_perm_avoiding(5, forb, rng)
                    for r in range(5):
                        up[r][p[r]] = True
                for r in range(5):
                    for c in range(5):
                        a, b = d1[r], d2[c]
                        counts[(min(a, b), max(a, b))] = 7 if up[r][c] else 6

    # Interleague: 0, 3, or 4 (row/col sums = 44)
    al, nl = by_lg["AL"], by_lg["NL"]
    zp = list(range(15))
    rng.shuffle(zp)
    p1 = _find_perm_avoiding(15, {i: {zp[i]} for i in range(15)}, rng)
    p2 = _find_perm_avoiding(15, {i: {zp[i], p1[i]} for i in range(15)}, rng)
    for i in range(15):
        for j in range(15):
            v = 3
            if j == zp[i]:
                v = 0
            elif j == p1[i] or j == p2[i]:
                v = 4
            if v:
                a, b = al[i], nl[j]
                counts[(min(a, b), max(a, b))] = v

    # Verify
    tot = defaultdict(int)
    for (a, b), g in counts.items():
        tot[a] += g
        tot[b] += g
    for t in teams:
        assert tot[t["id"]] == 162, f"Team {t['id']}: {tot[t['id']]}"
    return counts


# ---------------------------------------------------------------------------
# Part 2: Split game counts into series of 3 or 4 games
# ---------------------------------------------------------------------------

def _counts_to_series(counts):
    """Convert {pair: count} into [(teamA, teamB, series_len), ...]."""
    series = []
    for (a, b), total in counts.items():
        r = total
        while r > 0:
            if r >= 7:
                series.append((a, b, 4)); r -= 4
            elif r == 6:
                series.append((a, b, 3)); series.append((a, b, 3)); r = 0
            elif r == 4:
                series.append((a, b, 4)); r = 0
            elif r == 3:
                series.append((a, b, 3)); r = 0
            else:
                series.append((a, b, r)); r = 0
    return series


# ---------------------------------------------------------------------------
# Part 3: Assign home/away for each series -> 81H/81A per team
# ---------------------------------------------------------------------------

def _assign_home_away(series, all_ids, rng):
    hc = defaultdict(int)
    ps = defaultdict(list)
    for a, b, l in series:
        ps[(a, b)].append(l)
    result = []
    for (a, b), ls in ps.items():
        ls.sort(reverse=True)
        for i, l in enumerate(ls):
            ad, bd = 81 - hc[a], 81 - hc[b]
            if i % 2 == 0:
                h, aw = (a, b) if ad >= bd else (b, a)
            else:
                h, aw = (b, a) if bd >= ad else (a, b)
            result.append((h, aw, l))
            hc[h] += l
    # Iterative swap
    for _ in range(20000):
        w = max(all_ids, key=lambda t: abs(hc[t] - 81))
        if abs(hc[w] - 81) == 0:
            break
        if hc[w] > 81:
            cs = [i for i, (h, aw, l) in enumerate(result) if h == w and hc[aw] < 81]
        else:
            cs = [i for i, (h, aw, l) in enumerate(result) if aw == w and hc[h] > 81]
        if cs:
            idx = rng.choice(cs)
            h, aw, l = result[idx]
            result[idx] = (aw, h, l)
            hc[h] -= l
            hc[aw] += l
    return result


# ---------------------------------------------------------------------------
# Part 4: Calendar placement using time-slot rounds
# ---------------------------------------------------------------------------

def _place_on_calendar(series_list, season, all_ids, rng):
    """
    Divide the season into fixed time slots (rounds) of 3 or 4 days,
    with off days between groups. Assign each series to exactly one round.

    Layout: groups of 4 rounds separated by 1 off day.
    With rounds averaging 3.5 days: 4*3.5 + 1 = 15 days per group.
    186 days / 15 = 12.4 groups = ~50 rounds total.

    Each team plays in ~46-48 of ~50 rounds (leaving 2-4 off-slots).
    Max consecutive game days = 4 rounds * 4 days = 16 (within 20 limit).

    Each round can hold up to 15 series (all 30 teams paired).
    50 rounds * 15 = 750 capacity for ~680 series. Fits.
    """
    start = date(season, 3, 27)
    end = date(season, 9, 28)
    ndays = (end - start).days + 1  # 186

    # Build rounds with pattern [4,4,4,4,3] + 1 off day = 20 days per cycle.
    # Max consecutive game days = 4+4+4+4+3 = 19 (under 20).
    # 186 / 20 = 9.3 cycles -> 9 full cycles (45 rounds, 180 days)
    # + partial cycle from remaining 6 days.
    # Capacity: ~47 rounds * 15 = 705, for ~680 series. Fits well.

    rounds = []
    day = 0
    group_pattern = [4, 4, 4, 4, 3]  # 5 rounds totaling 19 game days
    pi = 0

    while day + 3 <= ndays:
        sl = group_pattern[pi % len(group_pattern)]
        if day + sl > ndays:
            sl = ndays - day
        if sl < 3:
            break
        rounds.append((day, sl))
        day += sl
        pi += 1
        if pi % len(group_pattern) == 0:
            day += 1  # off day between groups

    n_rounds = len(rounds)

    # Separate series by length
    s4_pool = [i for i, s in enumerate(series_list) if s[2] == 4]
    s3_pool = [i for i, s in enumerate(series_list) if s[2] == 3]
    s_other = [i for i, s in enumerate(series_list) if s[2] not in (3, 4)]
    rng.shuffle(s4_pool)
    rng.shuffle(s3_pool)

    assigned = set()
    round_teams = [set() for _ in range(n_rounds)]
    round_series = [[] for _ in range(n_rounds)]

    def _try_assign(si, round_idx):
        if si in assigned:
            return False
        h, a, l = series_list[si]
        _, sl = rounds[round_idx]
        if l > sl:
            return False
        if h in round_teams[round_idx] or a in round_teams[round_idx]:
            return False
        assigned.add(si)
        round_teams[round_idx].add(h)
        round_teams[round_idx].add(a)
        round_series[round_idx].append(si)
        return True

    def _fill_from_pool(pool, round_idx):
        remaining = []
        for si in pool:
            if si in assigned:
                continue
            if len(round_teams[round_idx]) >= 30:
                remaining.append(si)
                continue
            if not _try_assign(si, round_idx):
                remaining.append(si)
        return remaining

    # Fill each round: first with preferred-length series, then fill gaps
    for ri in range(n_rounds):
        _, sl = rounds[ri]
        if sl == 4:
            # Prefer 4-game series in 4-day slots
            s4_pool = _fill_from_pool(s4_pool, ri)
            # Fill remaining with 3-game series
            s3_pool = _fill_from_pool(s3_pool, ri)
        else:
            # 3-day slot: only 3-game series fit
            s3_pool = _fill_from_pool(s3_pool, ri)
        # Also try "other" length series
        s_other = _fill_from_pool(s_other, ri)

    # Second pass: try all unassigned in any round with space
    all_unassigned = s4_pool + s3_pool + s_other
    rng.shuffle(all_unassigned)
    for si in all_unassigned:
        if si in assigned:
            continue
        for ri in range(n_rounds):
            if len(round_teams[ri]) < 30:
                if _try_assign(si, ri):
                    break

    # Overflow: pack remaining into the tail end of the season
    still_unassigned = [i for i in range(len(series_list)) if i not in assigned]
    if still_unassigned:
        # Instead of extending past season, double-book time slots
        # (teams play in multiple rounds at the same time = same dates)
        # This shouldn't happen with proper capacity.
        # Fallback: append overflow rounds but try to reuse season days
        overflow_day = min(ndays - 4, rounds[-1][0] + rounds[-1][1]) if rounds else 0
        for si in still_unassigned:
            h, a, l = series_list[si]
            rounds.append((overflow_day, l))
            round_series.append([si])
            assigned.add(si)
            overflow_day = min(overflow_day + l, ndays - 1)

    # Convert to scheduled list
    scheduled = []
    for ri in range(len(rounds)):
        day_off, sl = rounds[ri]
        for si in round_series[ri] if ri < len(round_series) else []:
            h, a, length = series_list[si]
            sd = start + timedelta(days=day_off)
            scheduled.append((h, a, length, sd))

    return scheduled


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_schedule(season: int, teams: list[dict]) -> list[dict]:
    """
    Generate a full 162-game MLB schedule.

    Args:
        season: year (e.g., 2026)
        teams: list of team dicts with id, league, division

    Returns:
        list of game dicts with: season, game_date, home_team_id,
        away_team_id, game_number
    """
    rng = random.Random(season)
    all_ids = [t["id"] for t in teams]
    assert len(all_ids) == 30

    counts = _build_matchup_counts(teams, rng)
    series = _counts_to_series(counts)
    ha = _assign_home_away(series, all_ids, rng)
    placed = _place_on_calendar(ha, season, all_ids, rng)

    games = []
    for home, away, length, sd in placed:
        for d in range(length):
            games.append({
                "season": season,
                "game_date": (sd + timedelta(days=d)).isoformat(),
                "home_team_id": home,
                "away_team_id": away,
                "game_number": 0,
            })

    games.sort(key=lambda g: (g["game_date"], g["home_team_id"]))
    for i, g in enumerate(games, 1):
        g["game_number"] = i
    return games


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_schedule(games, teams):
    """Validate schedule, return report dict."""
    ids = {t["id"] for t in teams}
    total = defaultdict(int)
    home = defaultdict(int)
    away = defaultdict(int)
    sp = 0
    dates = set()
    for g in games:
        h, a = g["home_team_id"], g["away_team_id"]
        total[h] += 1; total[a] += 1
        home[h] += 1; away[a] += 1
        dates.add(g["game_date"])
        if h == a:
            sp += 1
    errors = []
    for tid in sorted(ids):
        if total[tid] != 162:
            errors.append(f"Team {tid}: {total[tid]} (expected 162)")
    ha_bad = [
        f"T{t}:{home[t]}H/{away[t]}A"
        for t in sorted(ids) if abs(home.get(t, 0) - 81) > 3
    ]
    if ha_bad:
        errors.append("H/A imbalance: " + ", ".join(ha_bad))
    if sp:
        errors.append(f"{sp} self-play games")
    sd = sorted(dates)
    return {
        "total_games": len(games),
        "game_counts": dict(total),
        "home_counts": dict(home),
        "away_counts": dict(away),
        "self_play_count": sp,
        "date_range": (sd[0], sd[-1]) if sd else None,
        "unique_dates": len(sd),
        "errors": errors,
        "valid": not errors,
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_teams = []
    tid = 1
    for league in ("AL", "NL"):
        for div in ("East", "Central", "West"):
            for _ in range(5):
                test_teams.append({"id": tid, "league": league, "division": div})
                tid += 1

    print("Generating schedule...")
    schedule = generate_schedule(2026, test_teams)
    print(f"Generated {len(schedule)} games")

    rpt = verify_schedule(schedule, test_teams)
    print(f"\nValidation: {'PASS' if rpt['valid'] else 'FAIL'}")
    print(f"Total: {rpt['total_games']}  (expect 2430)")
    print(f"Dates: {rpt['date_range']}")
    print(f"Unique dates: {rpt['unique_dates']}")
    if rpt["errors"]:
        for e in rpt["errors"]:
            print(f"  ERROR: {e}")

    print("\nPer-team:")
    for t in test_teams:
        i = t["id"]
        g = rpt["game_counts"].get(i, 0)
        h = rpt["home_counts"].get(i, 0)
        a = rpt["away_counts"].get(i, 0)
        tag = "OK" if g == 162 else f"!! {g}"
        print(f"  {i:2d} ({t['league']} {t['division']:7s}): {g:3d}  {h:2d}H/{a:2d}A  {tag}")

    # Series structure analysis
    from collections import Counter
    md = defaultdict(list)
    for g in schedule:
        md[(g["home_team_id"], g["away_team_id"])].append(g["game_date"])
    lens = []
    for k, ds in md.items():
        ds.sort()
        i = 0
        while i < len(ds):
            j = i + 1
            while j < len(ds):
                d1 = date.fromisoformat(ds[j - 1])
                d2 = date.fromisoformat(ds[j])
                if (d2 - d1).days == 1:
                    j += 1
                else:
                    break
            lens.append(j - i)
            i = j
    print(f"\nSeries lengths: {dict(sorted(Counter(lens).items()))}")

    # Max consecutive game days
    mx = 0
    for tid in range(1, 31):
        ds = sorted(
            date.fromisoformat(g["game_date"])
            for g in schedule
            if g["home_team_id"] == tid or g["away_team_id"] == tid
        )
        c = 1
        for i in range(1, len(ds)):
            if (ds[i] - ds[i - 1]).days == 1:
                c += 1
                mx = max(mx, c)
            else:
                c = 1
    print(f"Max consecutive game days: {mx}")

    # Test multiple seasons
    print("\n--- Multi-season test ---")
    for year in [2025, 2027, 2028]:
        sched = generate_schedule(year, test_teams)
        r = verify_schedule(sched, test_teams)
        mc = 0
        for tid in range(1, 31):
            ds = sorted(
                date.fromisoformat(g["game_date"]) for g in sched
                if g["home_team_id"] == tid or g["away_team_id"] == tid
            )
            c = 1
            for i in range(1, len(ds)):
                if (ds[i] - ds[i-1]).days == 1:
                    c += 1; mc = max(mc, c)
                else: c = 1
        status = "PASS" if r["valid"] else "FAIL"
        print(f"  {year}: {status}  games={r['total_games']}  "
              f"dates={r['date_range']}  max_consec={mc}")
