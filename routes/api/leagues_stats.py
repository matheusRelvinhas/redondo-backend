from datetime import datetime, timezone
from flask import Blueprint, request, Response, current_app
from models import LeaguesInfo, GamesInfo, db
from utils import responseApi
import requests

bp = Blueprint('leagues_stats', __name__, url_prefix='/api/leagues_stats')

import json

@bp.route('', methods=["GET"])
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
def league():
    slug = request.args.get('slug')
    if not slug:
        return responseApi({"error": "missing_slug"}, 400)
    cache_key = f"league_info::{slug}"
    cached = current_app.cache.get(cache_key)
    if cached:
        return responseApi(cached, 200)
    league = LeaguesInfo.query.filter_by(slug=slug).first()
    if not league:
        return responseApi({"error": "league_not_found"}, 404)
    current_app.cache.set(cache_key, league.to_dict(), timeout=20*60)
    return responseApi(league.to_dict(), 200)

@bp.route('/current', methods=["GET"])
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
        return responseApi(cached, 200)
    games = db.session.query(GamesInfo.status, GamesInfo.league_id).filter_by(status='current', league_id=league.league_id).all()
    is_current = False
    if len(games) >= 1:
        is_current = True
    current_app.cache.set(cache_key, {"current": is_current}, timeout=2*60)
    return responseApi({"current": is_current}, 200)

@bp.route('/finished', methods=["GET"])
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
        return responseApi(cached, 200)
    games = GamesInfo.query.filter_by(status='finished', league_id=league.league_id).all()
    games_list = [game.to_dict() for game in games]
    result = {"games": games_list}
    current_app.cache.set(cache_key, result, timeout=60*10)
    return responseApi(result, 200)

@bp.route('/upcoming', methods=["GET"])
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
        return responseApi(cached, 200)
    games = GamesInfo.query.filter_by(status='upcoming', league_id=league.league_id).all()
    games_list = [game.to_dict() for game in games]
    result = {"games": games_list}
    current_app.cache.set(cache_key, result, timeout=60 * 20)
    return responseApi(result, 200)

@bp.route('/league_image', methods=["GET"])
def league_image():
    slug = request.args.get('slug')
    if not slug:
        return responseApi({"error": "missing_slug"}, 400)
    cache_key = f"image_league::{slug}"
    cached_img = current_app.cache.get(cache_key)
    if cached_img:
        return Response(cached_img, mimetype="image/webp")
    query = LeaguesInfo.query
    league = query.filter(LeaguesInfo.slug == slug).first()
    if not league or not league.image_url:
        return responseApi({"error": "league_not_found"}, 404)
    try:
        res = requests.get(league.image_url, timeout=3)
        res.raise_for_status()
        current_app.cache.set(cache_key, res.content, timeout=1800)
        return Response(res.content, mimetype="image/webp")
    except requests.RequestException:
        return responseApi({"error": "failed_to_fetch_image"}, 502)
