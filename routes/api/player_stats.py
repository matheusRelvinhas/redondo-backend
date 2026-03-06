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
    current_app.cache.set(cache_key, result, timeout=60 * 20)
    return responseApi(result, 200)

@bp.route('/player', methods=["GET"])
def player():
    slug = request.args.get('slug')
    period = request.args.get('period')
    if not slug:
        return responseApi({"error": "missing_slug"}, 400)
    model_map = {
        '1': PlayerStatsLastMonth,
        '3': PlayerStats3Months,
        '6': PlayerStats6Months,
        '12': PlayerStats12Months
    }

    if period and period in model_map:
        periods_to_query = {period: model_map[period]}
        cache_suffix = period
    else:
        periods_to_query = model_map
        cache_suffix = "all"

    cache_key = f"player_info::{slug}::{cache_suffix}"
    cached = current_app.cache.get(cache_key)
    if cached:
        return responseApi(cached, 200)

    stats_list = []

    (
        nickname, first_name, last_name, 
        team_name, team_slug, img_url, 
        country_code, team_img_url, team_rank,
        team_points
    ) = (None,) * 10

    for period_key, model in periods_to_query.items():
        player = model.query.filter_by(slug=slug).first()
        if not player:
            continue

        player_data = player.to_dict()

        if not nickname:
            (
                nickname, first_name, last_name, 
                team_name, team_slug, img_url, 
                country_code, team_img_url, team_rank,
                team_points
            ) = (
                player_data['nickname'], player_data['first_name'], player_data['last_name'], 
                player_data['team_name'], player_data['team_slug'], player_data['img_url'],
                player_data['country_code'], player_data['team_img_url'], player_data['team_rank'],
                player_data['team_points']
            )

        player_data['period'] = period_key
        stats_list.append(player_data)

    if not stats_list:
        return responseApi({"error": "player_not_found"}, 404)

    result = {
        "slug": slug,
        "nickname": nickname,
        "first_name": first_name,
        "last_name": last_name,
        "team_slug": team_slug,
        "team_name": team_name,
        "img_url": img_url,
        "country_code": country_code,
        "team_img_url": team_img_url,
        "team_rank": team_rank,
        "team_points": team_points,
        "stats": stats_list
    }

    current_app.cache.set(cache_key, result, timeout=60 * 20)
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
