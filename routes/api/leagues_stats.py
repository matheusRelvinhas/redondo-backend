from datetime import datetime, timezone
from flask import Blueprint, request, current_app
from models import LeaguesInfo, GamesInfo, db
from utils import responseApi, token_service_required
import json

bp = Blueprint('leagues_stats', __name__, url_prefix='/api/leagues_stats')

@bp.route('', methods=["GET"])
@token_service_required
def get_leagues():
    status = request.args.get('status')
    years_param = request.args.get('years')
    if not status or not years_param:
        return responseApi({"error": "missing_arguments"}, 400)
    try:
        years = json.loads(years_param)
    except Exception:
        return responseApi({"error": "invalid_years_format"}, 400)
    if not years:
        return responseApi({"error": "missing_arguments"}, 400)
    cache_key = f"stats_leagues::{status}::{'-'.join(years)}"
    cached = current_app.cache.get(cache_key)
    if cached:
        current_app.limiter.limit("600 per 1 minutes")(lambda: None)()
        return responseApi(cached, 200)
    now_timestamp = int(datetime.now(timezone.utc).timestamp())
    leagues = LeaguesInfo.query.filter(LeaguesInfo.status == status).all()
    filtered_leagues = []
    for league in leagues:
        if league.start_date:
            try:
                start_dt = datetime.fromisoformat(league.start_date.replace('Z', '+00:00'))
                league_year = str(start_dt.year)
                league_ts = int(start_dt.timestamp())
                if league_year in years:
                    if status == 'upcoming' and league_ts < now_timestamp:
                        continue
                    filtered_leagues.append(league)
            except Exception:
                continue
    leagues = filtered_leagues
    result = {"leagues": [league.to_dict() for league in leagues]}
    current_app.cache.set(cache_key, result, timeout=20*60)
    return responseApi(result, 200)

@bp.route('/league', methods=["GET"])
@token_service_required
def league():
    slug = request.args.get('slug')
    if not slug:
        return responseApi({"error": "missing_slug"}, 400)
    cache_key = f"league_info::{slug}"
    cached = current_app.cache.get(cache_key)
    if cached:
        current_app.limiter.limit("600 per 1 minutes")(lambda: None)()
        return responseApi(cached, 200)
    league = LeaguesInfo.query.filter_by(slug=slug).first()
    if not league:
        return responseApi({"error": "league_not_found"}, 404)
    current_app.cache.set(cache_key, league.to_dict(), timeout=20*60)
    return responseApi(league.to_dict(), 200)

@bp.route('/current', methods=["GET"])
@token_service_required
def league_games_current():
    slug = request.args.get('slug')
    if not slug:
        return responseApi({"error": "missing_slug"}, 400)
    league = LeaguesInfo.query.filter_by(slug=slug).first()
    if not league:
        return responseApi({"error": "league_not_found"}, 404)
    cache_key = f"league_games_current::{slug}"
    cached = current_app.cache.get(cache_key)
    if cached:
        current_app.limiter.limit("600 per 1 minutes")(lambda: None)()
        return responseApi(cached, 200)
    games = db.session.query(GamesInfo.status, GamesInfo.league_id).filter_by(status='current', league_id=league.league_id).all()
    is_current = False
    if len(games) >= 1:
        is_current = True
    current_app.cache.set(cache_key, {"current": is_current}, timeout=10*60)
    return responseApi({"current": is_current}, 200)

@bp.route('/finished', methods=["GET"])
@token_service_required
def league_games_finished():
    slug = request.args.get('slug')
    if not slug:
        return responseApi({"error": "missing_slug"}, 400)
    cache_key = f"games_league::finished/{slug}"
    cached = current_app.cache.get(cache_key)
    league = LeaguesInfo.query.filter_by(slug=slug).first()
    if not league:
        return responseApi({"error": "league_not_found"}, 404)
    if cached:
        current_app.limiter.limit("600 per 1 minutes")(lambda: None)()
        return responseApi(cached, 200)
    games = GamesInfo.query.filter_by(status='finished', league_id=league.league_id).all()
    games_list = [game.to_dict() for game in games]
    result = {"games": games_list}
    current_app.cache.set(cache_key, result, timeout=60*10)
    return responseApi(result, 200)

@bp.route('/upcoming', methods=["GET"])
@token_service_required
def league_games_upcoming():
    slug = request.args.get('slug')
    if not slug:
        return responseApi({"error": "missing_slug"}, 400)
    cache_key = f"games_league::upcoming/{slug}"
    cached = current_app.cache.get(cache_key)
    league = LeaguesInfo.query.filter_by(slug=slug).first()
    if not league:
        return responseApi({"error": "league_not_found"}, 404)
    if cached:
        current_app.limiter.limit("600 per 1 minutes")(lambda: None)()
        return responseApi(cached, 200)
    games = GamesInfo.query.filter_by(status='upcoming', league_id=league.league_id).all()
    games_list = [game.to_dict() for game in games]
    result = {"games": games_list}
    current_app.cache.set(cache_key, result, timeout=60*20)
    return responseApi(result, 200)
