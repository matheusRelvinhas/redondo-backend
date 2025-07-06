import os
import sys
import requests
import time
from datetime import datetime, timedelta, timezone
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models import db, GamesInfo, TeamsInfo, PlayerStatsLastMonth, PlayerStats3Months, PlayerStats6Months, PlayerStats12Months, LeaguesInfo
from app import app
from sqlalchemy import or_

API_FINISHED_GAME_PART = "https://api.bo3.gg/api/v2/matches/finished?utc_offset=-10800&filter[tier][in]=s,a&filter[discipline_id][eq]=1&date="
API_UPCOMING_GAME_PART = "https://api.bo3.gg/api/v2/matches/upcoming?utc_offset=-10800&filter[tier][in]=s,a&filter[discipline_id][eq]=1&date="
API_LIVE_GAME_PART = "https://api.bo3.gg/api/v2/matches/live?utc_offset=-10800&filter[tier][in]=s,a&filter[discipline_id][eq]=1&date="
API_GAME_STATS_PART = "https://api.bo3.gg/api/v1/matches/"
API_MAP_GAME_STATS_PART = "https://api.bo3.gg/api/v1/games"
API_VALVE_RANKINK_PART = "https://api.bo3.gg/api/v1/teams/rankings/valve?scope=widget-teams-valve-rankings&sort=rank&filter[current][eq]=true&filter[region_str][eq]=world&with=team,team_valve_rankings_players"
API_TEAM_PART = "https://api.bo3.gg/api/v1/teams/earnings?filter[teams.discipline_id][eq]=1&with=country,active_players"
API_PLAYER_INFO_PART = "https://api.bo3.gg/api/v1/players/tops?sort=-avg_player_rating&filter[tournament_tier_rank][in]=1,2&filter[games_count][gte]=1"
API_FINISHED_LEAGUE_INFO_PART = "https://api.bo3.gg/api/v1/tournaments?scope=index-finished-tournaments&sort=-end_date&filter[tournaments.status][in]=finished&filter[tournaments.tier][in]=s,a&filter[tournaments.discipline_id][eq]=1&with=teams,tournament_prizes"
API_CURRENT_UPCOMING_LEAGUE_INFO_PART ="https://api.bo3.gg/api/v1/tournaments?scope=index-current-tournaments&sort=start_date&filter[tournaments.status][in]=current,upcoming&filter[tournaments.tier][in]=s,a&filter[tournaments.discipline_id][eq]=1&with=teams"

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def safe_get(obj, *keys):
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key)
        elif isinstance(obj, list) and isinstance(key, int) and 0 <= key < len(obj):
            obj = obj[key]
        else:
            return None
    return obj

def get_range(api_url, limit):
    max_range = None
    url_range = f"{api_url}&page[offset]=0&page[limit]={limit}"
    print(f"Getting range: {url_range}")
    try: 
        range_response = requests.get(url_range, timeout=60)
        range_response.raise_for_status()
        range_data = range_response.json()
        if safe_get(range_data, "total", "count"):
            max_range = safe_get(range_data, "total", "count") + (limit+1)
        return max_range
    except requests.RequestException as e:
        print(f"Error accessing {url_range}: {e}")

def get_oldest_date():
    games = db.session.query(GamesInfo).filter(GamesInfo.start_date != None).all()
    if games:
        oldest_game = max(
            games,
            key=lambda game: datetime.fromisoformat(game.start_date.replace("Z", "+00:00"))
        )
        dt = datetime.fromisoformat(oldest_game.start_date.replace("Z", "+00:00"))
    else:
        dt = datetime.now(timezone.utc) - timedelta(days=365)
    formatted_date = dt.strftime("%Y-%m-%d")
    return formatted_date

def iso_to_timestamp(iso_str: str) -> int:
    if not iso_str: return None
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return int(dt.timestamp())

def addOrAttGamesInfo(g):
    game = GamesInfo.query.filter_by(game_id=safe_get(g, "id")).first()
    game_data = {
        "game_id": safe_get(g, "id"),
        "slug": safe_get(g, "slug"),
        "status": safe_get(g, "status"),
        "parsed_status": safe_get(g, "parsed_status"),
        "bo_type": safe_get(g, "bo_type"),
        "winner_team_id": safe_get(g, "winner_team_id"),
        "tier": safe_get(g, "tier"),
        "start_date": safe_get(g, "start_date"),
        "end_date": safe_get(g, "end_date"),
        "start_timestamp": iso_to_timestamp(safe_get(g, "start_date")),
        "end_timestamp": iso_to_timestamp(safe_get(g, "end_date")),
        "team1_id": safe_get(g, "team1_id"),
        "team2_id": safe_get(g, "team2_id"),
        "team1_score": safe_get(g, "team1_score"),
        "team2_score": safe_get(g, "team2_score"),
        "league_id": safe_get(g, "tournament"),
        "games": safe_get(g, "games"),
    }
    if not game:
        game = GamesInfo(**game_data)
        db.session.add(game)
    else:
        for key, value in game_data.items():
            setattr(game, key, value)
    db.session.commit()

def get_url_att_game(url, date_str, is_live=False):
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        data = response.json()
        if is_live: games = safe_get(data, 'data')
        else: games = safe_get(data, 'data', 'tiers', 'high_tier', 'matches')    
        if games:
            for game in games:
                if not (safe_get(game, 'team1_id') and safe_get(game, 'team2_id')):
                    continue
                addOrAttGamesInfo(game)
        else: print(f"Don't have game_info at {date_str}")
    except requests.RequestException as e:
        print(f"Error accessing {url}: {e}")

def games_finished_info():
    start_day = datetime.strptime(get_oldest_date(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    today = datetime.now(timezone.utc)
    if (today - start_day).days < 7:
        start_day = today - timedelta(days=7)
    current_day = start_day
    while current_day <= today:
        date_str = current_day.strftime("%Y-%m-%d")
        url = f"{API_FINISHED_GAME_PART}{date_str}"
        print(f"Accessing: {url}")
        get_url_att_game(url, date_str)
        current_day += timedelta(days=1)

def games_upcoming_info():
    today = datetime.now(timezone.utc)
    end_day = today + timedelta(days=7)
    current_day = today
    while current_day < end_day:
        date_str = current_day.strftime("%Y-%m-%d")
        url = f"{API_UPCOMING_GAME_PART}{date_str}"
        print(f"Accessing: {url}")
        get_url_att_game(url, date_str)
        current_day += timedelta(days=1)

def games_live_info(count=20):
    today = datetime.now(timezone.utc)
    date_str = today.strftime("%Y-%m-%d")
    url = f"{API_LIVE_GAME_PART}{date_str}"
    for i in range(count):
        print(f"Accessing: {url}")
        get_url_att_game(url, date_str, True)
        if i <= count:
            time.sleep(90)

def games_stage_round():
    games = db.session.query(GamesInfo).filter(or_(GamesInfo.stage_round == None, GamesInfo.games_score == None)).all()
    for game in games:
        url = f"{API_GAME_STATS_PART}{game.slug}?scope=show-match&stream_language=en&with=games,teams,tournament_deep,stage,ai_predictions"
        print(f"Accessing: {url}")
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = response.json()
            gs_score = safe_get(data, "games")
            games_score = []
            if gs_score:
                for g_score in gs_score:
                    game_score = {
                        "map_name": (safe_get(g_score, "map_name")),
                        "order": (safe_get(g_score, "number")),
                        "rounds_count": (safe_get(g_score, "rounds_count")),
                        "winner_score": (safe_get(g_score, "winner_clan_score")),
                        "loser_score": (safe_get(g_score, "loser_clan_score")),
                        "winner_team": (safe_get(g_score, "winner_team_clan", "team", "slug")),
                    }
                    games_score.append(game_score)
                game.games_score = games_score
            stage_title = safe_get(data, "stage", "title")
            round_name = safe_get(data, "round", "name")
            if stage_title and round_name:
                stage_round = {
                    "stage": stage_title,
                    "round": round_name
                }
                game.stage_round = stage_round
                db.session.commit()
        except requests.RequestException as e:
            print(f"Error accessing {url}: {e}")

def addOrAttTeamsInfoValve(t):
    team = TeamsInfo.query.filter_by(slug=safe_get(t, "team", "slug")).first()
    team_data = {
        "team_id": safe_get(t, "team", "id"),
        "team_name": safe_get(t, "team_name"),
        "slug": safe_get(t, "team", "slug"),
        "points": safe_get(t, "points"),
        "rank": safe_get(t, "rank"),
        "country_name": safe_get(t, "team", "country", "name"),
        "country_code": safe_get(t, "team", "country", "code"),
        "region_code": safe_get(t, "region_code"),
        "team_valve_rankings_players": safe_get(t, "team_valve_rankings_players"),
        "image_url": safe_get(t, "team", "image_url"),
    }
    if not team:
        team = TeamsInfo(**team_data)
        db.session.add(team)
    else:
        for key, value in team_data.items():
            setattr(team, key, value)
    db.session.commit()

def team_info_valve_ranking():
    max_range = get_range(API_VALVE_RANKINK_PART, 30)
    for offset in range(0, max_range, 30):
        url = f"{API_VALVE_RANKINK_PART}&page[offset]={offset}&page[limit]=30"
        print(f"Accessing: {url}")
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = response.json()
            teams = safe_get(data, "results")
            for team in teams:
                addOrAttTeamsInfoValve(team)
        except requests.RequestException as e:
            print(f"Error accessing {url}: {e}")

def addOrAttTeamsInfo(t):
    team = TeamsInfo.query.filter_by(slug=safe_get(t, "slug")).first()
    team_data = {
        "team_id": safe_get(t, "id"),
        "team_name": safe_get(t, "name"),
        "slug": safe_get(t, "slug"),
        "country_name": safe_get(t, "country", "name"),
        "country_code": safe_get(t, "country", "code"),
        "image_url": safe_get(t, "image_url"),
    }
    if not team:
        team = TeamsInfo(**team_data)
        db.session.add(team)
    else:
        for key, value in team_data.items():
            setattr(team, key, value)
    db.session.commit()

def team_info():
    max_range = get_range(API_TEAM_PART, 30)
    for offset in range(0, max_range, 30):
        url = f"{API_TEAM_PART}&page[offset]={offset}&page[limit]=30"
        print(f"Accessing: {url}")
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = response.json()
            teams = safe_get(data, "results")
            for team in teams:
                addOrAttTeamsInfo(team)
        except requests.RequestException as e:
            print(f"Error accessing {url}: {e}")

def addOrAttPlayerStats(p, period):
    if (period == 'last_month'): playerDb = PlayerStatsLastMonth 
    elif (period == 'last_3_months'): playerDb = PlayerStats3Months 
    elif (period == 'last_6_months'): playerDb = PlayerStats6Months 
    elif (period == 'last_12_months'): playerDb = PlayerStats12Months 
    else: return None
    player = playerDb.query.filter_by(slug=safe_get(p, "player", "slug")).first()
    player_data = {
        "player_id": safe_get(p, "player", "id"),
        "nickname": safe_get(p, "player", "nickname"),
        "slug": safe_get(p, "player", "slug"),
        "first_name": safe_get(p, "player", "first_name"),
        "last_name": safe_get(p, "player", "last_name"),
        "country": safe_get(p, "player", "country", "name"),
        "country_code": safe_get(p, "player", "country", "code"),
        "region_id": safe_get(p, "player", "country", "region_id"),
        "team_id": safe_get(p, "player", "team_id"),
        "total_prize": safe_get(p, "player", "total_prize"),
        "image_url": safe_get(p, "player", "image_url"),
        "games_count": safe_get(p, "games_count"),
        "rounds_count": safe_get(p, "rounds_count"),
        "rounds_win": safe_get(p, "rounds_win"),
        "avg_player_rating_value": safe_get(p, "avg_player_rating_value"),
        "avg_player_rating": safe_get(p, "avg_player_rating"),
        "kills_sum": safe_get(p, "kills_sum"),
        "avg_kills": safe_get(p, "avg_kills"),
        "death_sum": safe_get(p, "death_sum"),
        "avg_death": safe_get(p, "avg_death"),
        "assists_sum": safe_get(p, "assists_sum"),
        "avg_assists": safe_get(p, "avg_assists"),
        "damage_sum": safe_get(p, "damage_sum"),
        "avg_damage": safe_get(p, "avg_damage"),
        "kd_diff_sum": safe_get(p, "kd_diff_sum"),
        "avg_kd_rate": safe_get(p, "avg_kd_rate"),
        "avg_first_kills": safe_get(p, "avg_first_kills"),
        "avg_first_death": safe_get(p, "avg_first_death"),
        "avg_trade_kills": safe_get(p, "avg_trade_kills"),
        "avg_trade_death": safe_get(p, "avg_trade_death"),
        "avg_multikills": safe_get(p, "avg_multikills"),
        "avg_shots": safe_get(p, "avg_shots"),
        "avg_shots_accuracy": safe_get(p, "avg_shots_accuracy"),
        "avg_headshots": safe_get(p, "avg_headshots"),
        "avg_headshots_accuracy": safe_get(p, "avg_headshots_accuracy"),
        "avg_headshot_kills_accuracy": safe_get(p, "avg_headshot_kills_accuracy"),
        "avg_flash_assists": safe_get(p, "avg_flash_assists"),
        "avg_flash_hits": safe_get(p, "avg_flash_hits"),
        "avg_flash_duration": safe_get(p, "avg_flash_duration"),
        "avg_he_damage": safe_get(p, "avg_he_damage"),
        "avg_molotov_damage": safe_get(p, "avg_molotov_damage"),
        "avg_kill_cost": safe_get(p, "avg_kill_cost"),
        "avg_hundred_damage_cost": safe_get(p, "avg_hundred_damage_cost"),
        "avg_saved": safe_get(p, "avg_saved"),
        "avg_multikills_vs_2": safe_get(p, "avg_multikills_vs_2"),
        "avg_multikills_vs_3": safe_get(p, "avg_multikills_vs_3"),
        "avg_multikills_vs_4": safe_get(p, "avg_multikills_vs_4"),
        "avg_multikills_vs_5": safe_get(p, "avg_multikills_vs_5"),
        "multikills_vs_2": safe_get(p, "multikills_vs_2"),
        "multikills_vs_3": safe_get(p, "multikills_vs_3"),
        "multikills_vs_4": safe_get(p, "multikills_vs_4"),
        "multikills_vs_5": safe_get(p, "multikills_vs_5"),
        "avg_clutches_vs_1": safe_get(p, "avg_clutches_vs_1"),
        "avg_clutches_vs_2": safe_get(p, "avg_clutches_vs_2"),
        "avg_clutches_vs_3": safe_get(p, "avg_clutches_vs_3"),
        "avg_clutches_vs_4": safe_get(p, "avg_clutches_vs_4"),
        "avg_clutches_vs_5": safe_get(p, "avg_clutches_vs_5"),
        "clutches_vs_1": safe_get(p, "clutches_vs_1"),
        "clutches_vs_2": safe_get(p, "clutches_vs_2"),
        "clutches_vs_3": safe_get(p, "clutches_vs_3"),
        "clutches_vs_4": safe_get(p, "clutches_vs_4"),
        "clutches_vs_5": safe_get(p, "clutches_vs_5"),
        "avg_ak47_kills": safe_get(p, "avg_ak47_kills"),
        "avg_ak47_damage": safe_get(p, "avg_ak47_damage"),
        "ak47_shots_accuracy": safe_get(p, "ak47_shots_accuracy"),
        "ak47_headshots_accuracy": safe_get(p, "ak47_headshots_accuracy"),
        "avg_m4a4_kills": safe_get(p, "avg_m4a4_kills"),
        "avg_m4a4_damage": safe_get(p, "avg_m4a4_damage"),
        "m4a4_shots_accuracy": safe_get(p, "m4a4_shots_accuracy"),
        "m4a4_headshots_accuracy": safe_get(p, "m4a4_headshots_accuracy"),
        "avg_m4a1_kills": safe_get(p, "avg_m4a1_kills"),
        "avg_m4a1_damage": safe_get(p, "avg_m4a1_damage"),
        "m4a1_shots_accuracy": safe_get(p, "m4a1_shots_accuracy"),
        "m4a1_headshots_accuracy": safe_get(p, "m4a1_headshots_accuracy"),
        "avg_awp_kills": safe_get(p, "avg_awp_kills"),
        "avg_awp_damage": safe_get(p, "avg_awp_damage"),
        "awp_shots_accuracy": safe_get(p, "awp_shots_accuracy"),
        "awp_headshots_accuracy": safe_get(p, "awp_headshots_accuracy"),
        "avg_galil_kills": safe_get(p, "avg_galil_kills"),
        "avg_galil_damage": safe_get(p, "avg_galil_damage"),
        "galil_shots_accuracy": safe_get(p, "galil_shots_accuracy"),
        "galil_headshots_accuracy": safe_get(p, "galil_headshots_accuracy"),
        "avg_aug_kills": safe_get(p, "avg_aug_kills"),
        "avg_aug_damage": safe_get(p, "avg_aug_damage"),
        "aug_shots_accuracy": safe_get(p, "aug_shots_accuracy"),
        "aug_headshots_accuracy": safe_get(p, "aug_headshots_accuracy"),
        "avg_desert_eagle_kills": safe_get(p, "avg_desert_eagle_kills"),
        "avg_desert_eagle_damage": safe_get(p, "avg_desert_eagle_damage"),
        "desert_eagle_shots_accuracy": safe_get(p, "desert_eagle_shots_accuracy"),
        "desert_eagle_headshots_accuracy": safe_get(p, "desert_eagle_headshots_accuracy"),
        "avg_usp_s_kills": safe_get(p, "avg_usp_s_kills"),
        "avg_usp_s_damage": safe_get(p, "avg_usp_s_damage"),
        "usp_s_shots_accuracy": safe_get(p, "usp_s_shots_accuracy"),
        "usp_s_headshots_accuracy": safe_get(p, "usp_s_headshots_accuracy"),
        "avg_glock_kills": safe_get(p, "avg_glock_kills"),
        "avg_glock_damage": safe_get(p, "avg_glock_damage"),
        "glock_shots_accuracy": safe_get(p, "glock_shots_accuracy"),
        "glock_headshots_accuracy": safe_get(p, "glock_headshots_accuracy"),
    }
    if not player:
        player = playerDb(**player_data)
        db.session.add(player)
    else:
        for key, value in player_data.items():
            setattr(player, key, value)
    db.session.commit()

def player_info_period(period=31, db_table='last_month'):
    today = datetime.now(timezone.utc) + timedelta(days=1)
    end_day = datetime.now(timezone.utc) - timedelta(days=period)
    date_prop = f"&filter[game_begin_at][gt]={end_day.strftime("%Y-%m-%d")}&filter[game_begin_at][lt]={today.strftime("%Y-%m-%d")}"
    max_range = get_range(f"{API_PLAYER_INFO_PART}{date_prop}&with=player", 50)
    for offset in range(0, max_range, 50):
        page_prop = f"&with=player&page[offset]={offset}&page[limit]=50"
        url = f"{API_PLAYER_INFO_PART}{date_prop}{page_prop}"
        print(f"Accessing: {url}")
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = response.json()
            players = safe_get(data, "results")
            for player in players:
                addOrAttPlayerStats(player, db_table)
        except requests.RequestException as e:
            print(f"Error accessing {url}: {e}")

def addOrAttLeaguesInfo(l):
    league = LeaguesInfo.query.filter_by(slug=safe_get(l, "slug")).first()
    league_data = {
        "league_id": safe_get(l, "id"),
        "name": safe_get(l, "name"),
        "slug": safe_get(l, "slug"),
        "status": safe_get(l, "status"),
        "prize": safe_get(l, "prize"),
        "start_date": safe_get(l, "start_date"),
        "start_timestamp": iso_to_timestamp(safe_get(l, "start_date")),
        "tier": safe_get(l, "tier"),
        "image_url": safe_get(l, "image_url"),
        "teams": safe_get(l, "teams"),
        "tournament_prizes": safe_get(l, "tournament_prizes"),
    }
    if not league:
        league = LeaguesInfo(**league_data)
        db.session.add(league)
    else:      
        for key, value in league_data.items():
            setattr(league, key, value)
    db.session.commit()

def leagues_finished_info():
    max_range = get_range(API_FINISHED_LEAGUE_INFO_PART, 50)
    for offset in range(0, max_range, 50):
        page_prop = f"&page[offset]={offset}&page[limit]=50"
        url = f"{API_FINISHED_LEAGUE_INFO_PART}{page_prop}"
        print(f"Accessing: {url}")
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = response.json()
            leagues = safe_get(data, "results")
            for league in leagues:
                addOrAttLeaguesInfo(league)
        except requests.RequestException as e:
            print(f"Error accessing {url}: {e}")

def leagues_current_upcoming_info():
    max_range = get_range(API_CURRENT_UPCOMING_LEAGUE_INFO_PART, 50)
    for offset in range(0, max_range, 50):
        page_prop = f"&page[offset]={offset}&page[limit]=50"
        url = f"{API_CURRENT_UPCOMING_LEAGUE_INFO_PART}{page_prop}"
        print(f"Accessing: {url}")
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = response.json()
            leagues = safe_get(data, "results")
            for league in leagues:
                addOrAttLeaguesInfo(league)
        except requests.RequestException as e:
            print(f"Error accessing {url}: {e}")
    
def playerStatsData(p, map_stats):
    playerData = {
        "name": safe_get(p, "steam_profile", "player", "nickname"),
        "slug": safe_get(p, "steam_profile", "player", "slug"),
        "country_code": safe_get(p, "steam_profile", "player", "country", "code"),
        "team_name": safe_get(p, "team_clan", "team", "name"),
        "team_slug": safe_get(p, "team_clan", "team", "slug"),
        "enemy_team_name": safe_get(p, "enemy_clan_name"),
        "kills": safe_get(p, "kills"),
        "death": safe_get(p, "death"),
        "assists": safe_get(p, "assists"),
        "headshots": safe_get(p, "headshots"),
        "first_kills": safe_get(p, "first_kills"),
        "first_death": safe_get(p, "first_death"),
        "trade_kills": safe_get(p, "trade_kills"),
        "trade_death": safe_get(p, "trade_death"),
        "kast": safe_get(p, "kast"),
        "player_rating": safe_get(p, "player_rating"),
        "adr": safe_get(p, "adr"),
        "hits": safe_get(p, "hits"),
        "shots": safe_get(p, "shots"),
        "got_damage": safe_get(p, "got_damage"),
        "damage": safe_get(p, "damage"),
        "multikills": safe_get(p, "multikills"),
        "utility_value": safe_get(p, "utility_value"),
        "money_spent": safe_get(p, "money_spent"),
        "money_save": safe_get(p, "money_save"),
        "clutches": safe_get(p, "clutches"),
        "total_equipment_value": safe_get(p, "total_equipment_value"),
        "additional_value": safe_get(p, "additional_value"),
        "pistols_value": safe_get(p, "pistols_value"),
        "weapons_value": safe_get(p, "weapons_value"),
        "player_rating_value": safe_get(p, "player_rating_value"),
    }
    if map_stats:
        playerData["cumulative_round_damages"] = p.get('cumulative_round_damages')
    return playerData

def games_players_stats():
    games = db.session.query(GamesInfo).filter(or_(GamesInfo.players_stats == None, GamesInfo.maps == None, GamesInfo.maps_players_stats == None))
    for game in games:
        url = f"{API_GAME_STATS_PART}{game.slug}/players_stats"
        print(f"Accessing: {url}")
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = response.json()
            players_stats = safe_get(data)
            if players_stats:
                maps = safe_get(players_stats[0], 'steam_profile', 'game_steam_profiles')
                p_maps = []
                for map in maps:
                    p_map = {
                        "map_name": safe_get(map, "map_name"),
                        "steam_game_id": safe_get(map, "game_id"),
                        "order": safe_get(map, "number")
                    }
                    p_maps.append(p_map)
                game.maps = p_maps
                p_stats = []
                for p in players_stats:
                    p_stats.append(playerStatsData(p, False))
                game.players_stats = p_stats
                db.session.commit()
                db.session.refresh(game)
                maps_p = []
                for m in game.maps:
                    if not safe_get(m, "steam_game_id"): continue
                    map_url = f"{API_MAP_GAME_STATS_PART}/{safe_get(m, "steam_game_id")}/players_stats"
                    print(f"Accessing: {map_url}")
                    map_obj = {
                        "map_name": safe_get(m, "map_name"),
                        "steam_game_id": safe_get(m, "steam_game_id"),
                        "players_stats": []
                    }
                    try:
                        map_response = requests.get(map_url, timeout=60)
                        map_response.raise_for_status()
                        map_data = map_response.json()
                        map_players_stats = safe_get(map_data)
                        for map_p in map_players_stats:
                            map_obj["players_stats"].append(playerStatsData(map_p, True))
                    except requests.RequestException as e:
                      print(f"Error accessing {url}: {e}")
                    maps_p.append(map_obj)
                game.maps_players_stats = maps_p
                db.session.commit()
        except requests.RequestException as e:
            print(f"Error accessing {url}: {e}")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            print("Erro ao enviar mensagem para o Telegram:", response.text)
    except Exception as e:
        print("Erro ao tentar enviar mensagem para o Telegram:", e)

FUNCTIONS = [
    ("leagues_finished_info", leagues_finished_info),
    ("leagues_current_upcoming_info", leagues_current_upcoming_info),
    ("team_info_valve_ranking", team_info_valve_ranking),
    ("team_info", team_info),
    ("player_info_period_31", lambda: player_info_period(31, 'last_month')),
    ("player_info_period_92", lambda: player_info_period(92, 'last_3_months')),
    ("player_info_period_183", lambda: player_info_period(183, 'last_6_months')),
    ("player_info_period_365", lambda: player_info_period(365, 'last_12_months')),
    ("games_finished_info", games_finished_info),
    ("games_upcoming_info", games_upcoming_info),
    ("games_stage_round", games_stage_round),
    ("games_players_stats", games_players_stats),
    ("games_live_info", lambda: games_live_info(20)),
]

def run_auto_db_loop():
    active_functions = FUNCTIONS.copy()
    while True:
        failed_functions = []
        success_count = 0
        for name, func in active_functions:
            try:
                func()
                success_count += 1
            except Exception as e:
                error_msg = f"⚠️ Erro na função '{name}':\n{str(e)}"
                send_telegram(error_msg)
                failed_functions.append(name)
        active_functions = [f for f in active_functions if f[0] not in failed_functions]
        summary = (
            f"✅ Ciclo finalizado.\n"
            f"✔️ Funções OK: {success_count}\n"
            f"❌ Funções removidas: {len(failed_functions)}: {failed_functions}\n"
        )
        send_telegram(summary)
        time.sleep(5)

with app.app_context():
    run_auto_db_loop()