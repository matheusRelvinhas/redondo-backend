from flask import Blueprint, request, Response, current_app
from models import PlayerStatsLastMonth, PlayerStats3Months, PlayerStats6Months, PlayerStats12Months
from utils import responseApi
import requests

bp = Blueprint('player_stats', __name__, url_prefix='/api/player_stats')

@bp.route('', methods=["GET"])
def player_stats():
    period = request.args.get('period')
    game_count = request.args.get('game_count')
    if not period or not game_count:
        return responseApi({"error": "missing_arguments"}, 400)
    cache_key = f"stats_player::{period}::{game_count}"
    cached = current_app.cache.get(cache_key)
    if cached:
        return responseApi(cached, 200)
    model = {
        'last_month': PlayerStatsLastMonth,
        '3_months': PlayerStats3Months,
        '6_months': PlayerStats6Months,
        '12_months': PlayerStats12Months
    }.get(period)
    if not model:
        return responseApi({"error": "invalid_period"}, 400)
    players = model.query.filter(model.games_count >= game_count).all()
    result = {"players": [p.to_dict() for p in players]}
    current_app.cache.set(cache_key, result, timeout=600)
    return responseApi(result, 200)

@bp.route('/player', methods=["GET"])
def player():
    slug = request.args.get('slug')
    if not slug:
        return responseApi({"error": "missing_slug"}, 400)
    cache_key = f"player_info::{slug}"
    cached = current_app.cache.get(cache_key)
    if cached:
        return responseApi(cached, 200)
    model_map = {
        'last_month': PlayerStatsLastMonth,
        '3_months': PlayerStats3Months,
        '6_months': PlayerStats6Months,
        '12_months': PlayerStats12Months
    }
    result = {
        "slug": slug,
        "periods": {}
    }
    for period_key, model in model_map.items():
        player = model.query.filter_by(slug=slug).first()
        if player:
            result["periods"][period_key] = player.to_dict()
    if not result["periods"]:
        return responseApi({"error": "player_not_found"}, 404)
    current_app.cache.set(cache_key, result, timeout=600)
    return responseApi(result, 200)
    

@bp.route('/player_image', methods=["GET"])
def player_image():
    slug = request.args.get('slug')
    period = request.args.get('period')
    if not slug:
        return responseApi({"error": "missing_slug"}, 400)
    cache_key = f"image_player::{slug}::{period or 'all'}"
    cached_img = current_app.cache.get(cache_key)
    if cached_img:
        return Response(cached_img, mimetype="image/webp")
    model_map = {
        'last_month': PlayerStatsLastMonth,
        '3_months': PlayerStats3Months,
        '6_months': PlayerStats6Months,
        '12_months': PlayerStats12Months
    }
    player = None
    if period:
        model = model_map.get(period)
        if not model:
            return responseApi({"error": "invalid_period"}, 400)
        player = model.query.filter_by(slug=slug).first()
    else:
        for model in model_map.values():
            player = model.query.filter_by(slug=slug).first()
            if player:
                break
    if not player or not player.image_url:
        return responseApi({"error": "player_not_found"}, 404)
    try:
        res = requests.get(player.image_url, timeout=3)
        res.raise_for_status()
        current_app.cache.set(cache_key, res.content, timeout=1800)
        return Response(res.content, mimetype="image/webp")
    except requests.RequestException:
        return responseApi({"error": "failed_to_fetch_image"}, 502)
