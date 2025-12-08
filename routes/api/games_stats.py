from flask import Blueprint, request, current_app
from models import db, GamesInfo, LeaguesInfo, TeamsInfo
from utils import responseApi
from datetime import datetime, timedelta
import pytz

bp = Blueprint('games_stats', __name__, url_prefix='/api/games_stats')

@bp.route('', methods=["GET"])
def games_stats():
    period = request.args.get('period')
    league = request.args.get('league')
    if not period and not league:
        return responseApi({"error": "missing_arguments"}, 400)
    cache_key = f"games_stats::{period or league}"
    cached = current_app.cache.get(cache_key)
    if cached:
        return responseApi(cached, 200)
    brasil_tz = pytz.timezone('America/Sao_Paulo')
    now = datetime.now(brasil_tz)
    if league:
        if league=='not_league':
            return responseApi({"games": []}, 200)
        league_obj = LeaguesInfo.query.filter_by(slug=league).first()
        if not league_obj:
            return responseApi({"error": "league_not_found"}, 404)
        games = GamesInfo.query.filter_by(
            status='finished',
            league_id=league_obj.league_id
        ).all()
        filtered_games = [game.to_dict() for game in games]
    else:
        if period == 'last_7':
            seven_days_ago = now - timedelta(days=7)
            games = GamesInfo.query.filter_by(status='finished').all()
            filtered_games = []
            for game in games:
                if not game.start_date:
                    continue
                try:
                    start_dt = datetime.fromisoformat(game.start_date.replace('Z', '+00:00'))
                    start_dt = start_dt.astimezone(brasil_tz)
                    if seven_days_ago <= start_dt <= now:
                        filtered_games.append(game.to_dict())
                except ValueError:
                    continue
        else:
            games = GamesInfo.query.filter(
                GamesInfo.status == 'finished',
                GamesInfo.start_date.contains(period)
            ).all()
            filtered_games = [game.to_dict() for game in games]
    result = {"games": filtered_games}
    current_app.cache.set(cache_key, result, timeout=60*10)
    return responseApi(result, 200)

@bp.route('/current', methods=["GET"])
def games_current():
    games = GamesInfo.query.filter_by(status='current').all()
    games_list = [game.to_dict() for game in games]
    cache_key = f"games_stats::current"
    cached = current_app.cache.get(cache_key)
    if cached:
        return responseApi(cached, 200)
    current_app.cache.set(cache_key, {"games": games_list}, timeout=2*10)
    return responseApi({"games": games_list}, 200)

@bp.route('/upcoming', methods=["GET"])
def games_upcoming():
    cache_key = "games_stats::upcoming"
    cached = current_app.cache.get(cache_key)
    if cached:
        return responseApi(cached, 200)
    games = GamesInfo.query.filter_by(status='upcoming').all()
    games_list = [game.to_dict() for game in games]
    result = {"games": games_list}
    current_app.cache.set(cache_key, result, timeout=60 * 20)
    return responseApi(result, 200)

@bp.route('/periods', methods=["GET"])
def games_periods():
    cache_key = "games_periods::"
    cached = current_app.cache.get(cache_key)
    if cached:
        return responseApi(cached, 200)
    games = GamesInfo.query.with_entities(GamesInfo.start_date).all()
    periods_set = set()
    for (start_date,) in games:
        if not start_date:
            continue
        try:
            dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            period_str = dt.strftime('%Y-%m')
            periods_set.add(period_str)
        except ValueError:
            continue
    periods = sorted(periods_set, reverse=True)
    current_app.cache.set(cache_key, periods, timeout=60*10)
    return responseApi(periods, 200)

@bp.route("/leagues", methods=["GET"])
def games_leagues():
    cache_key = "games_leagues::"
    cached = current_app.cache.get(cache_key)
    if cached:
        return responseApi(cached, 200)
    subq = (
        db.session.query(GamesInfo.league_id)
        .filter(GamesInfo.league_id.isnot(None))
        .distinct()
        .subquery()
    )
    leagues = (
        db.session.query(LeaguesInfo.slug, LeaguesInfo.name, LeaguesInfo.start_timestamp)
        .filter(LeaguesInfo.league_id.in_(db.session.query(subq.c.league_id)))
        .order_by(LeaguesInfo.name.asc())  
        .all()
    )
    result = [{"slug": slug, "name": name, "start_timestamp": start_timestamp} for slug, name, start_timestamp in leagues]
    current_app.cache.set(cache_key, result, timeout=60*10)
    return responseApi(result, 200)

@bp.route("/teams", methods=["GET"])
def games_teams():
    cache_key = "games_teams::"
    cached = current_app.cache.get(cache_key)
    if cached:
        return responseApi(cached, 200)
    games = db.session.query(GamesInfo.team1_id, GamesInfo.team2_id).all()
    team_ids = set()
    for team1_id, team2_id in games:
        if team1_id:
            team_ids.add(team1_id)
        if team2_id:
            team_ids.add(team2_id)
    if not team_ids:
        return responseApi([], 200)
    teams = (
        db.session.query(TeamsInfo.slug, TeamsInfo.team_name)
        .filter(TeamsInfo.team_id.in_(team_ids))
        .all()
    )
    result = [{"slug": slug, "name": name} for slug, name in teams]
    current_app.cache.set(cache_key, result, timeout=60*10)
    return responseApi(result, 200)
