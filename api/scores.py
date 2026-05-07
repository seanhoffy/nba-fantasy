from flask import Flask, jsonify
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

app = Flask(__name__)

ESPN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

PLAYER_ESPN_IDS = {
    "Shai Gilgeous-Alexander": "4278073",
    "LeBron James": "1966",
    "Jaden McDaniels": "4431671",
    "Dylan Harper": "5037871",
    "Alex Caruso": "2991350",
    "Isaiah Joe": "4395702",
    "Cade Cunningham": "4432166",
    "De'Aaron Fox": "4066259",
    "Tyrese Maxey": "4431678",
    "Ayo Dosunmu": "4397002",
    "Paul George": "4251",
    "Luke Kennard": "3913174",
    "Chet Holmgren": "4433255",
    "Jalen Duren": "4433621",
    "Josh Hart": "3062679",
    "Jarrett Allen": "4066328",
    "Julian Champagnie": "4592479",
    "Cason Wallace": "4683692",
    "Jalen Brunson": "3934672",
    "Stephon Castle": "4845367",
    "Isaiah Hartenstein": "4222252",
    "Daniss Jenkins": "5107199",
    "Kelly Oubre Jr.": "3133603",
    "Rui Hachimura": "4066648",
    "Karl-Anthony Towns": "3136195",
    "Julius Randle": "3064514",
    "Ausar Thompson": "4684742",
    "Naz Reid": "4396971",
    "VJ Edgecombe": "5124612",
    "Luke Kornet": "3064560",
    "Anthony Edwards": "4594268",
    "Tobias Harris": "6440",
    "Ajay Mitchell": "4900671",
    "Duncan Robinson": "3157465",
    "Jared McCain": "4683778",
    "Deandre Ayton": "4278129",
    "James Harden": "3992",
    "Evan Mobley": "4432158",
    "Keldon Johnson": "4395723",
    "Isaiah Stewart": "4432810",
    "Max Strus": "4065778",
    "Marcus Smart": "2990992",
    "Victor Wembanyama": "5104157",
    "OG Anunoby": "3934719",
    "Devin Vassell": "4395630",
    "Mikal Bridges": "3147657",
    "Terrence Shannon Jr.": "4432847",
    "Mitchell Robinson": "4351852",
    "Donovan Mitchell": "3908809",
    "Jalen Williams": "4593803",
    "Rudy Gobert": "3032976",
    "Joel Embiid": "3059318",
    "Austin Reaves": "4066457",
    "Luguentz Dort": "4397020",
}

ROSTERS = {
    "Chase":   ["Shai Gilgeous-Alexander", "LeBron James", "Jaden McDaniels", "Dylan Harper", "Alex Caruso", "Isaiah Joe"],
    "Kieran":  ["Cade Cunningham", "De'Aaron Fox", "Tyrese Maxey", "Ayo Dosunmu", "Paul George", "Luke Kennard"],
    "Cooper":  ["Chet Holmgren", "Jalen Duren", "Josh Hart", "Jarrett Allen", "Julian Champagnie", "Cason Wallace"],
    "Keith":   ["Jalen Brunson", "Stephon Castle", "Isaiah Hartenstein", "Daniss Jenkins", "Kelly Oubre Jr.", "Rui Hachimura"],
    "Sean":    ["Karl-Anthony Towns", "Julius Randle", "Ausar Thompson", "Naz Reid", "VJ Edgecombe", "Luke Kornet"],
    "Kriteen": ["Anthony Edwards", "Tobias Harris", "Ajay Mitchell", "Duncan Robinson", "Jared McCain", "Deandre Ayton"],
    "Kobe":    ["James Harden", "Evan Mobley", "Keldon Johnson", "Isaiah Stewart", "Max Strus", "Marcus Smart"],
    "Parker":  ["Victor Wembanyama", "OG Anunoby", "Devin Vassell", "Mikal Bridges", "Terrence Shannon Jr.", "Mitchell Robinson"],
    "Trent":   ["Donovan Mitchell", "Jalen Williams", "Rudy Gobert", "Joel Embiid", "Austin Reaves", "Luguentz Dort"],
}

REB_IDX, AST_IDX, PTS_IDX = 7, 8, 13


def safe_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def fetch_player_gamelog(player_name):
    espn_id = PLAYER_ESPN_IDS.get(player_name)
    if not espn_id:
        return {"name": player_name, "nba_team": "", "pts": 0, "reb": 0, "ast": 0, "gp": 0, "pra": 0}

    try:
        resp = requests.get(
            f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{espn_id}/gamelog",
            params={"season": "2026", "seasontype": "3"},
            headers=ESPN_HEADERS,
            timeout=10,
        )
        data = resp.json()
    except Exception as e:
        return {"name": player_name, "nba_team": "", "pts": 0, "reb": 0, "ast": 0, "gp": 0, "pra": 0}

    events_dict = data.get("events", {})
    season_types = data.get("seasonTypes", [])
    nba_team = season_types[0].get("displayTeam", "") if season_types else ""
    pts = reb = ast = gp = 0

    for st in season_types:
        for cat in st.get("categories", []):
            cat_name = cat.get("displayName", "")
            is_r1 = "Quarterfinal" in cat_name
            is_r2 = "Semifinal" in cat_name
            is_r3_plus = "Conference Finals" in cat_name or "NBA Finals" in cat_name

            if not (is_r1 or is_r2 or is_r3_plus):
                continue
            if is_r1:
                continue

            for ev in cat.get("events", []):
                event_id = ev.get("eventId", "")
                event_note = events_dict.get(event_id, {}).get("eventNote", "")
                if is_r2 and "Game 1" in event_note:
                    continue
                stats = ev.get("stats", [])
                if len(stats) > PTS_IDX:
                    pts += safe_int(stats[PTS_IDX])
                    reb += safe_int(stats[REB_IDX])
                    ast += safe_int(stats[AST_IDX])
                    gp += 1

    return {"name": player_name, "nba_team": nba_team, "pts": pts, "reb": reb, "ast": ast, "gp": gp, "pra": pts + reb + ast}


def get_scores():
    all_players = [p for roster in ROSTERS.values() for p in roster]
    player_stats = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_player_gamelog, name): name for name in all_players}
        for future in as_completed(futures):
            result = future.result()
            player_stats[result["name"]] = result

    teams = []
    for team_name, roster in ROSTERS.items():
        players = [player_stats.get(p, {"name": p, "nba_team": "", "pts": 0, "reb": 0, "ast": 0, "gp": 0, "pra": 0}) for p in roster]
        players.sort(key=lambda x: x["pra"], reverse=True)
        teams.append({"team": team_name, "total": sum(p["pra"] for p in players), "players": players})

    teams.sort(key=lambda x: x["total"], reverse=True)
    return teams


@app.route("/api/scores")
def scores():
    data = get_scores()
    return jsonify({"data": data, "updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")})
