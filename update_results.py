#!/usr/bin/env python3
"""
Updates results.json from football-data.org (free tier covers the FIFA World Cup).

Usage:  FOOTBALL_DATA_API_KEY=xxxx python3 scripts/update_results.py

Scoring model expected by index.html:
  { "Nation": { "gw": <group-stage wins>, "stage": "group|r32|r16|qf|sf|fourth|third|runnerup|champion" } }

The script is deliberately paranoid: if it sees a team name it can't map to the
site's 48 nations, it exits non-zero WITHOUT writing, so a bad feed can never
corrupt the leaderboard.
"""
import json, os, sys, urllib.request, datetime

API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY")
if not API_KEY:
    sys.exit("Set FOOTBALL_DATA_API_KEY")

COMPETITION = "WC"  # FIFA World Cup on football-data.org
URL = f"https://api.football-data.org/v4/competitions/{COMPETITION}/matches"

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_PATH = os.path.join(HERE, "results.json")

# football-data.org name -> site name (extend if the feed surprises us)
ALIASES = {
    "Czech Republic": "Czechia",
    "Ivory Coast": "Côte d'Ivoire",
    "Cote d'Ivoire": "Côte d'Ivoire",
    "USA": "United States",
    "United States of America": "United States",
    "Korea Republic": "South Korea",
    "Republic of Korea": "South Korea",
    "Bosnia-Herzegovina": "Bosnia & Herzegovina",
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Turkey": "Türkiye",
    "Cabo Verde": "Cape Verde",
    "IR Iran": "Iran",
    "Congo DR": "DR Congo",
    "DR Congo": "DR Congo",
    "Democratic Republic of the Congo": "DR Congo",
}

# football-data.org stage -> site stage reached by *playing in* that round
STAGE_REACHED = {
    "LAST_32": "r32",
    "ROUND_OF_32": "r32",
    "LAST_16": "r16",
    "ROUND_OF_16": "r16",
    "QUARTER_FINALS": "qf",
    "SEMI_FINALS": "sf",
}
STAGE_ORDER = ["group", "r32", "r16", "qf", "sf", "fourth", "third", "runnerup", "champion"]

# football-data.org stage -> short stage key used by the Match Centre tab
STAGE_KEY = {
    "GROUP_STAGE": "g",
    "LAST_32": "r32", "ROUND_OF_32": "r32",
    "LAST_16": "r16", "ROUND_OF_16": "r16",
    "QUARTER_FINALS": "qf",
    "SEMI_FINALS": "sf",
    "THIRD_PLACE": "3rd",
    "FINAL": "final",
}


def canon(name: str, valid: set) -> str:
    name = ALIASES.get(name, name)
    if name not in valid:
        sys.exit(f"Unmapped team name from feed: '{name}'. Add it to ALIASES.")
    return name


def soft_name(raw, valid: set, status: str):
    """Map a feed name for the matches list. Same paranoia as canon() for
    FINISHED matches; for scheduled/in-play knockouts the feed may carry
    placeholders, which we pass through as None (the site shows its own
    bracket labels instead)."""
    if not raw:
        return None
    name = ALIASES.get(raw, raw)
    if name in valid:
        return name
    if status == "FINISHED":
        sys.exit(f"Unmapped team name from feed: '{raw}'. Add it to ALIASES.")
    return None


def collect_matches(data, valid):
    """Flatten the feed into the per-match list consumed by the Matches tab."""
    out = []
    for m in data.get("matches", []):
        st = STAGE_KEY.get(m.get("stage", ""))
        if not st:
            continue
        status = m.get("status", "")
        home = soft_name(m.get("homeTeam", {}).get("name"), valid, status)
        away = soft_name(m.get("awayTeam", {}).get("name"), valid, status)
        sc = m.get("score", {}) or {}
        ft = sc.get("fullTime", {}) or {}
        wflag = sc.get("winner")
        winner = home if wflag == "HOME_TEAM" else away if wflag == "AWAY_TEAM" else None
        entry = {
            "st": st,
            "utc": m.get("utcDate"),
            "status": status,
            "h": home, "a": away,
            "hs": ft.get("home"), "as": ft.get("away"),
        }
        if st == "g":
            grp = (m.get("group") or "").replace("Group ", "").strip()
            if grp:
                entry["g"] = grp
        dur = sc.get("duration")
        if dur == "PENALTY_SHOOTOUT":
            pens = sc.get("penalties", {}) or {}
            entry["dur"] = "pens"
            entry["hp"] = pens.get("home")
            entry["ap"] = pens.get("away")
        elif dur == "EXTRA_TIME":
            entry["dur"] = "aet"
        if winner:
            entry["w"] = winner
        out.append(entry)
    out.sort(key=lambda x: (x["utc"] or ""))
    return out


def bump(results: dict, team: str, stage: str):
    if STAGE_ORDER.index(stage) > STAGE_ORDER.index(results[team]["stage"]):
        results[team]["stage"] = stage


def main():
    current = json.load(open(RESULTS_PATH, encoding="utf-8"))
    valid = set(current["results"].keys())
    results = {k: {"gw": 0, "gd": 0, "gl": 0, "stage": "group", "out": False} for k in valid}

    req = urllib.request.Request(URL, headers={"X-Auth-Token": API_KEY})
    data = json.loads(urllib.request.urlopen(req, timeout=30).read())

    for m in data.get("matches", []):
        if m.get("status") != "FINISHED":
            continue
        stage = m.get("stage", "")
        home = canon(m["homeTeam"]["name"], valid)
        away = canon(m["awayTeam"]["name"], valid)
        winner_flag = m.get("score", {}).get("winner")  # HOME_TEAM | AWAY_TEAM | DRAW
        winner = home if winner_flag == "HOME_TEAM" else away if winner_flag == "AWAY_TEAM" else None
        loser = away if winner == home else home if winner == away else None

        if stage == "GROUP_STAGE":
            if winner:
                results[winner]["gw"] += 1
                results[loser]["gl"] += 1
            else:
                results[home]["gd"] += 1
                results[away]["gd"] += 1
        elif stage in STAGE_REACHED:
            bump(results, home, STAGE_REACHED[stage])
            bump(results, away, STAGE_REACHED[stage])
            # winners of QF reach sf; winners of earlier rounds get bumped when
            # their next match appears, but bump now so the board moves same-night:
            nxt = {"r32": "r16", "r16": "qf", "qf": "sf"}.get(STAGE_REACHED[stage])
            if winner and nxt:
                bump(results, winner, nxt)
            if loser:
                results[loser]["out"] = True
        elif stage == "THIRD_PLACE":
            if winner and loser:
                bump(results, winner, "third")
                bump(results, loser, "fourth")
                results[winner]["out"] = True
                results[loser]["out"] = True
        elif stage == "FINAL":
            if winner and loser:
                bump(results, winner, "champion")
                bump(results, loser, "runnerup")
                results[loser]["out"] = True

    r32_teams = set()
    for m in data.get("matches", []):
        if m.get("stage") in ("LAST_32", "ROUND_OF_32"):
            for side in ("homeTeam", "awayTeam"):
                nm = m[side].get("name")
                if nm:
                    r32_teams.add(canon(nm, valid))
    if r32_teams:
        for t in valid:
            if t not in r32_teams and results[t]["stage"] == "group":
                results[t]["out"] = True

    matches = collect_matches(data, valid)

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%d %B, %H:%M UTC")
    json.dump({"lastUpdated": now, "results": results, "matches": matches},
              open(RESULTS_PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"results.json updated at {now} ({len(matches)} matches in feed)")


if __name__ == "__main__":
    main()
