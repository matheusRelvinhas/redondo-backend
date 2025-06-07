import os
from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import traceback
import time
import json
import gzip
from io import BytesIO
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models import  TeamsStats, PlayerStatsLastMonth, PlayerStats3Months, PlayerStats6Months, PlayerStats12Months, LeaguesInfo, GamesInfo, db
from app import app
from datetime import datetime, timedelta
import requests
import re
from sqlalchemy import or_, and_
import platform

PERIODS = ["last_month" ,"last_3_months", "last_6_months", "last_12_months"]

MAX_FAILS = 10
MAX_COUNTS_RESTART = 5
DEFAULT_SLEEP = 10
DEFAULT_SLEEP_INTERVAL = 60

TEAMS_MAX_PAGES = 15
TEAMS_API_URL_PART = "https://api.bo3.gg/api/v1/teams/rankings/valve"

PLAYERS_MAX_PAGES = 20
PLAYERS_API_URL_PART = "https://api.bo3.gg/api/v1/players/tops"

LEAGUES_MAX_PAGES = 10
LEAGUES_API_URL_PART = "https://api.bo3.gg/api/v1/tournaments"
LEAGUES_STAGE_API_URL_PART = "https://api.bo3.gg/api/v1/matches"

GAMES_API_URL_PART = "https://api.bo3.gg/api/v2/matches/finished"
GAMES_STATS_API_URL_PART = "https://api.bo3.gg/api/v1/matches"
GAMES_PLAYERS_STATS_API_URL_PART = "https://api.bo3.gg/api/v1/games"

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

def addOrAttTeamsStats(t):
    team = TeamsStats.query.filter_by(team_id=t["team"]["id"]).first()
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
        team = TeamsStats(**team_data)
        db.session.add(team)
    else:
        for key, value in team_data.items():
            setattr(team, key, value)
    db.session.commit()

def getTeamsStats():
    count_restart = 0
    for page in range(1, TEAMS_MAX_PAGES + 1):
        print(f"\n🌐 Acessando Valve - página times {page}")
        url = f"https://bo3.gg/pt/teams/valve-rankings/world?page={page}"
        driver.get(url)
        time.sleep(DEFAULT_SLEEP)
        for request in driver.requests:
            if request.response and TEAMS_API_URL_PART in request.url and "date_filter" not in request.url:
                print(f"\n🔗 URL da requisição interceptada: {request.url}")
                print(f"📦 Status: {request.response.status_code}")
                compressed = BytesIO(request.response.body)
                with gzip.GzipFile(fileobj=compressed) as f:
                    json_data = f.read().decode("utf-8")
                data = json.loads(json_data)   
                for t in data["results"]:
                    addOrAttTeamsStats(t)
                print(f"Banco de dados atualizado, 📄 Dados JSON")
        count_restart += 1
        if count_restart >= MAX_COUNTS_RESTART:
            count_restart = 0
            restart_driver()
        time.sleep(2)
        
def addOrAttPlayerStats(p, period):
    if (period == 'last_month'): playerDb = PlayerStatsLastMonth 
    elif (period == 'last_3_months'): playerDb = PlayerStats3Months 
    elif (period == 'last_6_months'): playerDb = PlayerStats6Months 
    elif (period == 'last_12_months'): playerDb = PlayerStats12Months 
    else: return None
    player = playerDb.query.filter_by(player_id=p["player"]["id"]).first()
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

def getPlayersStats(period):
    count_restart = 0
    for page in range(1, PLAYERS_MAX_PAGES + 1):
        print(f"\n🌐 Acessando período '{period}' - página jogadores {page}")
        url = f"https://bo3.gg/pt/players?period={period}&tiers=s,a&tab=main&sort=rating&order=desc&games_count=5&page={page}"
        driver.get(url)
        time.sleep(DEFAULT_SLEEP)
        for request in driver.requests:
            if request.response and PLAYERS_API_URL_PART in request.url:
                print(f"\n🔗 URL da requisição interceptada: {request.url}")
                print(f"📦 Status: {request.response.status_code}")
                compressed = BytesIO(request.response.body)
                with gzip.GzipFile(fileobj=compressed) as f:
                    json_data = f.read().decode("utf-8")
                data = json.loads(json_data)          
                for p in data["results"]:
                    addOrAttPlayerStats(p, period)
                print(f"Banco de dados atualizado, 📄 Dados JSON")
        count_restart += 1
        if count_restart >= MAX_COUNTS_RESTART:
            count_restart = 0
            restart_driver()
        time.sleep(2)

def addOrAttLeaguesInfo(l):
    league = LeaguesInfo.query.filter_by(league_id=l["id"]).first()
    league_data = {
        "league_id": safe_get(l, "id"),
        "name": safe_get(l, "name"),
        "slug": safe_get(l, "slug"),
        "status": safe_get(l, "status"),
        "prize": safe_get(l, "prize"),
        "start_date": safe_get(l, "start_date"),
        "tier": safe_get(l, "tier"),
        "pickem_presence": safe_get(l, "pickem_presence"),
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

def getLeaguesInfo(status):
    count_restart = 0
    for page in range(1, LEAGUES_MAX_PAGES + 1):
        print(f"\n🌐 Acessando ligas - {status} - página ligas {page}")
        url = f"https://bo3.gg/pt/tournaments/{status}?tiers=s,a&page={page}"
        driver.get(url)
        time.sleep(DEFAULT_SLEEP)
        for request in driver.requests:
            if request.response and LEAGUES_API_URL_PART in request.url and status in request.url:
                print(f"\n🔗 URL da requisição interceptada: {request.url}")
                print(f"📦 Status: {request.response.status_code}")
                compressed = BytesIO(request.response.body)
                with gzip.GzipFile(fileobj=compressed) as f:
                    json_data = f.read().decode("utf-8")
                data = json.loads(json_data) 
                for l in data["results"]:
                    addOrAttLeaguesInfo(l)
                print(f"Banco de dados atualizado, 📄 Dados JSON")
        count_restart += 1
        if count_restart >= MAX_COUNTS_RESTART:
            count_restart = 0
            restart_driver()
        time.sleep(2)

RANDOM_ID_SLUG_PATTERN = re.compile(r'^[a-f0-9]{8,}-vs-[a-f0-9]{8,}-\d{2}-\d{2}-\d{4}$')

def getLeaguesGamesRounds(status):
    count_restart = 0
    if status == 'finished':
        current_year = str(datetime.now().year)
        previous_year = str(int(current_year) - 1)
        query = db.session.query(LeaguesInfo).filter(
            or_(
                and_(LeaguesInfo.stage_rounds == None, LeaguesInfo.status == status),
                LeaguesInfo.status == 'current'
            )
        )
        query = query.filter(
            or_(
                LeaguesInfo.start_date.ilike(f"%{current_year}%"),
                LeaguesInfo.start_date.ilike(f"%{previous_year}%")
            )
        )
    elif status == 'current':
        query = db.session.query(LeaguesInfo).filter(LeaguesInfo.status == status)
    filtered_leagues = query.all()
    print(f"Total de ligas: {len(filtered_leagues)} para atualizar - {status}")
    for league in filtered_leagues:
        stage_rounds = []
        print(f"\n🌐 Acessando liga - {league.slug} - {status}")
        print(league.slug)
        url = f"https://bo3.gg/pt/tournaments/{league.slug}/{'results' if status=='finished' else 'matches'}"
        driver.get(url)
        time.sleep(DEFAULT_SLEEP)
        for request in driver.requests:
            if request.response and LEAGUES_STAGE_API_URL_PART in request.url:
                print(f"\n🔗 URL da requisição interceptada: {request.url}")
                print(f"📦 Status: {request.response.status_code}")
                compressed = BytesIO(request.response.body)
                with gzip.GzipFile(fileobj=compressed) as f:
                    json_data = f.read().decode("utf-8")
                data = json.loads(json_data)
                for l in data["results"]:
                    if safe_get(l, "tournament", "slug") == league.slug:
                        slug = safe_get(l, "slug")
                        stage = safe_get(l, "stage", "title") or safe_get(l, "round", "stages")
                        round_name = safe_get(l, "round", "name")
                        if slug and RANDOM_ID_SLUG_PATTERN.match(slug):
                            continue
                        if stage and round_name:
                            new_stage_round = {
                                "slug": slug,
                                "stage": stage,
                                "round": round_name,
                                "team1_slug": safe_get(l, "team1", "slug"),
                                "team2_slug": safe_get(l, "team2", "slug"),
                                "start_date": safe_get(l, "start_date"),
                                "bo_type": safe_get(l, "bo_type"),
                                "tier": safe_get(l, "tier"),
                            }
                            exists = False
                            for i, existing_round in enumerate(stage_rounds):
                                if existing_round["slug"] == slug:
                                    stage_rounds[i] = new_stage_round
                                    exists = True
                                    break
                            if not exists:
                                stage_rounds.append(new_stage_round)
        league.stage_rounds = stage_rounds
        db.session.commit()
        print(f"Banco de dados atualizado, 📄 Dados JSON")
        count_restart += 1
        if count_restart >= MAX_COUNTS_RESTART:
            count_restart = 0
            restart_driver()
        time.sleep(2)

def extract_date_from_slug(slug):
    match = re.search(r'(\d{2}-\d{2}-\d{4})$', slug)
    if match:
        return datetime.strptime(match.group(1), "%d-%m-%Y")
    return None

def get_oldest_game_date():
    games = db.session.query(GamesInfo.slug).all()
    extracted_dates = [extract_date_from_slug(slug) for (slug,) in games if extract_date_from_slug(slug)]
    return min(extracted_dates) if extracted_dates else None

def get_latest_game_date():
    games = db.session.query(GamesInfo.slug).all()
    extracted_dates = [extract_date_from_slug(slug) for (slug,) in games if extract_date_from_slug(slug)]
    return max(extracted_dates) if extracted_dates else None

def addOrAttGamesInfo(g):
    game = GamesInfo.query.filter_by(game_id=g["id"]).first()
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
        "team1_id": safe_get(g, "team1_id"),
        "team2_id": safe_get(g, "team2_id"),
        "team1_score": safe_get(g, "team1_score"),
        "team2_score": safe_get(g, "team2_score"),
        "live_coverage": safe_get(g, "live_coverage"),
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

def scrape_matches_between_dates(start_date, end_date, reverse=False):
    count_restart = 0
    days_range = (start_date - end_date).days if reverse else (end_date - start_date).days
    print(f"🔍 Loop de scraping {'⬇️ decrescente' if reverse else '⬆️ crescente'}: de {start_date.date()} até {end_date.date()} ({days_range + 1} dias)")
    for i in range(days_range + 1):
        date = (start_date - timedelta(days=i)) if reverse else (start_date + timedelta(days=i))
        formatted_date = date.strftime("%Y-%m-%d")
        print(f"\n🌐 Acessando jogos finalizados - Data: {formatted_date}")
        url = f"https://bo3.gg/pt/matches/finished?tiers=s,a&period=all_time&date={formatted_date}"
        driver.get(url)
        time.sleep(DEFAULT_SLEEP)
        for request in driver.requests:
            if request.response and GAMES_API_URL_PART in request.url:
                print(f"\n🔗 URL da requisição interceptada: {request.url}")
                print(f"📦 Status: {request.response.status_code}")
                compressed = BytesIO(request.response.body)
                with gzip.GzipFile(fileobj=compressed) as f:
                    json_data = f.read().decode("utf-8")
                data = json.loads(json_data)
                tiers = data["data"].get("tiers", {})
                high_tier = tiers.get("high_tier")
                if high_tier and "matches" in high_tier:
                    for g in high_tier["matches"]:
                        addOrAttGamesInfo(g)
                print("Banco de dados atualizado, 📄 Dados JSON")
                time.sleep(2)
    count_restart += 1
    if count_restart >= MAX_COUNTS_RESTART:
        count_restart = 0
        restart_driver()
    time.sleep(2)

seen_game_ids = set()

def getGamesFinishedInfo():
    today = datetime.today()
    one_year_ago = today - timedelta(days=365)
    oldest_date = get_oldest_game_date()
    if oldest_date:
        if oldest_date > one_year_ago:
            scrape_matches_between_dates(oldest_date, one_year_ago, reverse=True)
        else:
            print("✅ Banco já cobre um ano ou mais no passado.")
    else:
        print("❌ Nenhuma data no banco. Iniciando scraping completo do último ano.")
        scrape_matches_between_dates(today, one_year_ago, reverse=True)
    latest_date = get_latest_game_date()
    if latest_date:
        if latest_date.date() < today.date():
            next_day = latest_date + timedelta(days=1)
            scrape_matches_between_dates(next_day, today, reverse=False)
        elif latest_date.date() == today.date():
            scrape_matches_between_dates(today, today, reverse=False)
    else:
        scrape_matches_between_dates(today, today, reverse=False)
    print("✅ Nenhuma data futura para atualizar.")

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

def wait_for_request(slug, match=True, max_attempts=5, wait_interval=0.5):
    attempts = 0
    while attempts < max_attempts:
        time.sleep(wait_interval)
        if driver.requests:
            try:
                for request in driver.requests:
                    if not request.response or not hasattr(request, "url"):
                        continue
                    if match and f"{GAMES_STATS_API_URL_PART}/{slug}/players_stats" in request.url:
                        return request
                    elif not match and "players_stats" in request.url and GAMES_PLAYERS_STATS_API_URL_PART in request.url:
                        try:
                            game_id = request.url.split("/games/")[1].split("/")[0]
                            if game_id not in seen_game_ids:
                                seen_game_ids.add(game_id)
                                return request
                        except IndexError:
                            continue
            except Exception as e:
                print(f"⚠️ Erro ao verificar requests: {e}")
        print(f"⏳ Tentativa {attempts + 1}/{max_attempts} falhou. Tentando novamente...")
        attempts += 1
    print("⏳ Timeout: não foi possível capturar a requisição esperada.")
    return None

def getGamesFinishedStats():
    query = db.session.query(GamesInfo).filter(
        or_(
            GamesInfo.players_stats == None, 
            GamesInfo.maps_players_stats == None,
        )
    )
    query = query.filter(GamesInfo.parsed_status != 'rejected')
    games_missing_stats = query.all()
    for idx, game in enumerate(games_missing_stats):
        if idx % 10 == 0 and idx > 0:
            restart_driver()
        driver.requests.clear()
        print(f"\n🌐 Acessando estatística jogo - {game.slug}")
        url = f"https://bo3.gg/pt/matches/{game.slug}"
        driver.get(url)
        print("⏳ Aguardando players_stats do jogo...")
        request = wait_for_request(game.slug, match=True)
        if not request:
            print(f"🚨 Timeout ao aguardar stats do jogo {game.slug}. Recarregando...")
            driver.refresh()
            request = wait_for_request(game.slug, match=True)
            if not request:
                print(f"❌ Falha persistente. Pulando o jogo {game.slug}.")
                continue
        print(f"\n🔗 URL da requisição interceptada: {request.url}")
        print(f"📦 Status: {request.response.status_code}")
        compressed = BytesIO(request.response.body)
        with gzip.GzipFile(fileobj=compressed) as f:
            json_data = f.read().decode("utf-8")
        data = json.loads(json_data)
        players_stats = []
        for p in data:
            player_stats = playerStatsData(p, False)
            players_stats.append(player_stats)
        game.players_stats = players_stats
        db.session.commit()
        maps = [g["map_name"] for g in game.games if "map_name" in g and g.get("state") != "error"]
        maps_players_stats = []
        for map in maps:
            print(f"\n🌐 Acessando estatística round {game.slug} - {map}")
            url = f"https://bo3.gg/pt/matches/{game.slug}/{map.removeprefix('de_')}"
            driver.get(url)
            print("⏳ Aguardando players_stats do round...")
            request = wait_for_request(game.slug, match=False)
            if not request:
                print(f"🚨 Timeout no round {map}. Recarregando...")
                driver.refresh()
                request = wait_for_request(game.slug, match=False)
                if not request:
                    print(f"❌ Falha persistente no round {map}. Pulando...")
                    continue
            print(f"\n🔗 URL da requisição interceptada: {request.url}")
            print(f"📦 Status: {request.response.status_code}")
            compressed = BytesIO(request.response.body)
            with gzip.GzipFile(fileobj=compressed) as f:
                json_data = f.read().decode("utf-8")
            data = json.loads(json_data)
            m_players_stats = []
            for p in data:
                m_player_stats = playerStatsData(p, True)
                m_players_stats.append(m_player_stats)
            maps_players_stats.append({
                "map": map,
                "stats": m_players_stats
            })
        game.maps_players_stats = maps_players_stats
        db.session.commit()
        print(f"✅ Banco de dados atualizado, 📄 Dados JSON")
        time.sleep(2)

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


def run_tasks():
    tasks = [
        getGamesFinishedInfo,
        getGamesFinishedStats,
        lambda: getLeaguesInfo('current'),
        lambda: getLeaguesInfo('finished'),
        lambda: getLeaguesGamesRounds('current'),
        lambda: getLeaguesGamesRounds('finished'),
        getTeamsStats,
        *[lambda p=period: getPlayersStats(p) for period in PERIODS],
    ]
    for task in tasks:
        task()

TEMP_PROFILE_DIR = "./chrome_temp_profile"

service = None
driver = None
fail_count = 0

def get_chrome_options():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--disable-accelerated-2d-canvas")
    chrome_options.add_argument("--disable-accelerated-video-decode")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--disable-xnnpack")
    chrome_options.add_argument("--disable-speech-api")
    chrome_options.add_argument("--incognito") 
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-client-side-phishing-detection")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_experimental_option('excludeSwitches', ['disable-default-browser-check', 'enable-logging'])
    chrome_options.add_argument("--silent")
    return chrome_options

def kill_chrome_processes():
    system = platform.system()
    if system == "Windows":
        print('Developemnt not kill proccess')
        #os.system("taskkill /f /im chrome.exe >nul 2>&1")
        #os.system("taskkill /f /im chromedriver.exe >nul 2>&1")
    else:
        print('Developemnt not kill proccess')
        #os.system("pkill chrome > /dev/null 2>&1")
        #os.system("pkill chromedriver > /dev/null 2>&1")

def restart_driver(show_log=True):
    global driver, service
    if show_log:
        print(f"\n🔄 Reiniciando driver preventivamente (limpeza completa)... [{datetime.now().strftime('%H:%M:%S')}]")
    try:
        if driver:
            driver.quit()
    except Exception as e:
        print(f"⚠️ Erro ao fechar o driver: {e}")
    try:
        kill_chrome_processes()
    except Exception as e:
        print(f"⚠️ Erro ao matar processos: {e}")
    try:
        if service:
            service.stop()
    except Exception:
        pass
    service = Service(ChromeDriverManager().install(), log_output=os.devnull)
    driver = webdriver.Chrome(service=service, options=get_chrome_options())
    print(f"✅ Driver iniciado com sucesso. [{datetime.now().strftime('%H:%M:%S')}]")
    return driver

def run_automation():
    global driver, fail_count
    with app.app_context():
        try:
            driver = restart_driver()
            print(f"\n🕒 Execução iniciada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            run_tasks()
            print("✅ Todas tarefas concluídas com sucesso.")
            send_telegram("✅ Banco de dados atualizado. Próxima execução em 30 minutos.")
            return True
        except Exception as e:
            print(f"\n🚨 Erro na automação: {e}")
            print(traceback.format_exc())
            fail_count += 1
            if fail_count >= MAX_FAILS:
                send_telegram(f"🚨 Falha crítica: {fail_count} tentativas consecutivas.\nErro: {str(e)[:200]}")
            return False
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

while True:
    success = run_automation()
    if success:
        time.sleep(30 * DEFAULT_SLEEP_INTERVAL)
    else:
        wait_time = min(fail_count * 5, 300)
        print(f"⏳ Aguardando {wait_time}s antes de tentar novamente...")
        time.sleep(wait_time)