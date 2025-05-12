from flask import Blueprint, request
from models import PlayerStats6Months, PlayerStats12Months
from utils import responseApi

bp = Blueprint('player_stats', __name__, url_prefix='/api/player_stats')

@bp.route('/', methods=["GET"])
def player_stats():
    period = request.args.get('period')
    game_count = request.args.get('game_count')

    if not period or not game_count:
        return responseApi({"error": "missing_arguments"}, 400)

    model = {
        '6_months': PlayerStats6Months,
        '12_months': PlayerStats12Months
    }.get(period)

    if not model:
        return responseApi({"error": "invalid_period"}, 400)

    players = model.query.filter(model.games_count >= game_count).all()
    return responseApi({"players": [p.to_dict() for p in players]}, 200)
