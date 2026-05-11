from flask import Blueprint, request, current_app
from models import PlayerStatsLastMonth, PlayerStats3Months, PlayerStats6Months, PlayerStats12Months
from utils import responseApi, token_service_required, cache_return

def player_info(periods_to_query, slug):
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
    return result

bp = Blueprint('player_stats', __name__, url_prefix='/api/player_stats')

@bp.route('', methods=["GET"])
@token_service_required
@cache_return(timeout=20*60)
def player_stats():
    period = request.args.get('period')
    game_count = request.args.get('game_count')
    if not period or not game_count:
        return responseApi({"error": "missing_arguments"}, 400)
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
    return responseApi(result, 200)

@bp.route('/player', methods=["GET"])
@token_service_required
@cache_return(timeout=20*60)
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
    else:
        periods_to_query = model_map
    result = player_info(periods_to_query, slug)
    if not result['stats']:
        return responseApi({"error": "player_not_found"}, 404)
    return responseApi(result, 200)
