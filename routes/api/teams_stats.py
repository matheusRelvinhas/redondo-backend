import time
from flask import Blueprint, request, current_app
from models import TeamsInfo, PlayerStats12Months, PlayerStats6Months, PlayerStats3Months, PlayerStatsLastMonth, GamesInfo, LeaguesInfo, db
from utils import responseApi, token_service_required, cache_return
from sqlalchemy import String, cast, func

bp = Blueprint('teams_stats', __name__, url_prefix='/api/teams_stats')

def get_team_info(slug):
    team = db.session.query(TeamsInfo).filter_by(slug=slug).first()
    if not team:
        return responseApi({"error": "team_not_found"}, 400)
    return team

def get_team_players_info(team_id):
    stat_models = {
        "12_months": PlayerStats12Months,
        "6_months":  PlayerStats6Months,
        "3_months":  PlayerStats3Months,
        "last_month": PlayerStatsLastMonth
    }
    players_map = {}
    for key, ModelClass in stat_models.items():
        stats_list = db.session.query(ModelClass).filter_by(team_id=team_id).all()
        for stat in stats_list:
            if stat.slug not in players_map:
                players_map[stat.slug] = {
                    "slug": stat.slug,
                    "12_months": None, "6_months": None, "3_months": None, "last_month": None
                }
            players_map[stat.slug][key] = stat.to_dict()
    return list(players_map.values())

def calculate_win_percentage(win, lose):
    total = win + lose
    if total == 0:
        return 0
    return round((win*100) / total)

def get_team_games_info(slug):
    now = time.time()
    periods = {
        "12_months": now - (365 * 24 * 60 * 60),
        "6_months":  now - (182 * 24 * 60 * 60),
        "3_months":  now - (91 * 24 * 60 * 60),
        "last_month": now - (30 * 24 * 60 * 60),
    }
    wl_info = {
        "12_months": {"win": 0, "lose": 0, "performance": 0},
        "6_months":  {"win": 0, "lose": 0, "performance": 0},
        "3_months":  {"win": 0, "lose": 0, "performance": 0},
        "last_month": {"win": 0, "lose": 0, "performance": 0}
    }
    one_year_ago = periods["12_months"]
    team1 = func.substring_index(GamesInfo.slug, '-rs-', 1)
    team2_raw = func.substring_index(GamesInfo.slug, '-rs-', -1)
    team2 = func.regexp_replace(team2_raw, r'-[0-9]{2}-[0-9]{2}-[0-9]{4}$', '')
    last_games = db.session.query(GamesInfo).filter(
        GamesInfo.status == 'finished',
        GamesInfo.start_timestamp >= one_year_ago,
        (team1 == slug) | (team2 == slug)
    ).all()
    for game in last_games:
        if not game.start_timestamp:
            continue
        winner_team_slug = None
        if game.winner_team_id:
            winner_team = db.session.query(TeamsInfo).filter_by(team_id=game.winner_team_id).first()
            if winner_team:
                winner_team_slug = winner_team.slug
        for period_name, threshold_timestamp in periods.items():
            if game.start_timestamp >= threshold_timestamp:
                if winner_team_slug == slug:
                    wl_info[period_name]["win"] += 1
                else:
                    wl_info[period_name]["lose"] += 1
    for period_name in wl_info.keys():
        win = wl_info[period_name]["win"]
        lose = wl_info[period_name]["lose"]
        total = win + lose
        wl_info[period_name]["performance"] = round((win * 100) / total) if total > 0 else 0
    return {
        "games": [game.to_dict() for game in last_games],
        "wl_info": wl_info
    }

def get_team_maps_info(games):
    maps_list = []
    for game in games:
        if not game.get("games_score"):
            continue
        for map_score in game['games_score']:
            map_info = map_score.copy()
            map_info['game_slug'] = game.get('slug')
            map_info['start_timestamp'] = (game.get('start_timestamp') or 0) + (map_score.get('order') or 0)
            map_info['team1_name'] = game.get('team1_name')
            map_info['team2_name'] = game.get('team2_name')
            map_info['team1_slug'] = game.get('team1_slug')
            map_info['team2_slug'] = game.get('team2_slug')
            map_info['team1_score'] = game.get('team1_score')
            map_info['team2_score'] = game.get('team2_score')
            map_info['team1_img_url'] = game.get('team1_img_url')
            map_info['team2_img_url'] = game.get('team2_img_url')
            maps_list.append(map_info)
    return maps_list

def get_team_leagues_info(slug):
    search_pattern = f'%"slug": "{slug}"%'
    one_year_ago = time.time() - (365 * 24 * 60 * 60)
    leagues_query = db.session.query(LeaguesInfo).filter(
        cast(LeaguesInfo.teams, String).like(search_pattern),
        LeaguesInfo.start_timestamp >= one_year_ago,
        LeaguesInfo.status.in_(['finished', 'current'])
    ).all()
    return [l.to_dict() for l in leagues_query]

@bp.route('', methods=["GET"])
@token_service_required
@cache_return(timeout=20*60)
def get_teams():
    region_code = request.args.get('region_code')
    if not region_code:
        return responseApi({"error": "missing_arguments"}, 400)
    subquery = (
        db.session.query(
            TeamsInfo.rank,
            func.max(TeamsInfo.updated_at).label('max_updated_at')
        )
        .group_by(TeamsInfo.rank)
        .subquery()
    )
    query = db.session.query(TeamsInfo).join(
        subquery,
        db.and_(
            TeamsInfo.rank == subquery.c.rank,
            TeamsInfo.updated_at == subquery.c.max_updated_at
        )
    )
    if region_code != 'all':
        query = query.filter(TeamsInfo.region_code == region_code)
    teams = query.all()
    result = {"teams": [team.to_dict() for team in teams]}
    return responseApi(result, 200)

@bp.route('/team', methods=["GET"])
@token_service_required
@cache_return(timeout=20*60)
def team_info():
    slug = request.args.get('slug')
    if not slug:
        return responseApi({"error": "missing_arguments"}, 400)
    games_info = get_team_games_info(slug)
    team = get_team_info(slug)
    players_data = get_team_players_info(team.team_id)
    leagues_list = get_team_leagues_info(slug)
    result = {
        "team": team.to_dict(),
        "players": players_data,
        "games": games_info["games"],
        "maps": get_team_maps_info(games_info["games"]),
        "leagues": leagues_list
    }
    return responseApi(result, 200)
