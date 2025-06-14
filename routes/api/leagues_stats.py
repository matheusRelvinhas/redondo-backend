from datetime import datetime, timezone
from flask import Blueprint, request, Response, current_app
from models import LeaguesInfo
from utils import responseApi
import requests

bp = Blueprint('leagues_stats', __name__, url_prefix='/api/leagues_stats')

import json

@bp.route('/', methods=["GET"])
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
                        continue  # ignora ligas com data passada
                    filtered_leagues.append(league)
            except Exception:
                continue
    leagues = filtered_leagues
    result = {"leagues": [league.to_dict() for league in leagues]}
    current_app.cache.set(cache_key, result, timeout=600)
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
