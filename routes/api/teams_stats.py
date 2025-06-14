from flask import Blueprint, request, Response, current_app
from models import TeamsInfo, db
from utils import responseApi
import requests
from sqlalchemy import desc, func

bp = Blueprint('teams_stats', __name__, url_prefix='/api/teams_stats')

@bp.route('/', methods=["GET"])
def get_teams():
    region_code = request.args.get('region_code')
    cache_key = f"stats_teams::{region_code or 'all'}"
    cached = current_app.cache.get(cache_key)
    if cached:
        return responseApi(cached, 200)
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
    current_app.cache.set(cache_key, result, timeout=600)
    return responseApi(result, 200)

@bp.route('/team_image', methods=["GET"])
def team_image():
    slug = request.args.get('slug')
    if not slug:
        return responseApi({"error": "missing_slug"}, 400)
    cache_key = f"image_team::{slug}"
    cached_img = current_app.cache.get(cache_key)
    if cached_img:
        return Response(cached_img, mimetype="image/webp")
    query = TeamsInfo.query
    team = query.filter(TeamsInfo.slug == slug).first()
    if not team or not team.image_url:
        return responseApi({"error": "team_not_found"}, 404)
    try:
        res = requests.get(team.image_url, timeout=3)
        res.raise_for_status()
        current_app.cache.set(cache_key, res.content, timeout=1800)
        return Response(res.content, mimetype="image/webp")
    except requests.RequestException:
        return responseApi({"error": "failed_to_fetch_image"}, 502)
