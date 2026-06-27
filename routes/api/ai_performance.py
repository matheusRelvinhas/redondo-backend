from flask import Blueprint
from models import GamesInfo
from utils import responseApi, token_service_required, cache_return
from sqlalchemy import and_, or_

bp = Blueprint('ai_performance', __name__, url_prefix='/api/ai_performance')

def parse_prediction(prediction_str):
    try:
        parts = prediction_str.strip().split('-')
        return int(parts[0]), int(parts[1])
    except:
        return None, None

def get_valid_scores_for_bo(bo_type):
    if bo_type == 1:
        return {(1, 0), (0, 1)}
    elif bo_type == 3:
        return {(2, 0), (2, 1), (1, 2), (0, 2)}
    elif bo_type == 5:
        return {(3, 0), (3, 1), (3, 2), (2, 3), (1, 3), (0, 3)}
    return None

def calculate_prediction_results(team1_score, team2_score, ai_predictions, bo_type):
    exact_result = False
    win_result = False
    if not ai_predictions or team1_score is None or team2_score is None:
        return exact_result, win_result
    pred_t1, pred_t2 = parse_prediction(ai_predictions)
    if pred_t1 is None:
        return exact_result, win_result
    valid_scores = get_valid_scores_for_bo(bo_type)
    if valid_scores and (pred_t1, pred_t2) not in valid_scores:
        return exact_result, win_result
    exact_result = (pred_t1 == team1_score and pred_t2 == team2_score)
    real_winner = 1 if team1_score > team2_score else 2
    pred_winner = 1 if pred_t1 > pred_t2 else 2
    win_result = (real_winner == pred_winner)
    return exact_result, win_result

@bp.route('', methods=["GET"])
@token_service_required
@cache_return(timeout=60*60*6)
def games_stats():
    games = GamesInfo.query.filter(
        and_(
            GamesInfo.status == 'finished',
            GamesInfo.parsed_status == 'done',
            or_(
                GamesInfo.ai_predictions.isnot(None),
                GamesInfo.redondo_predictions.isnot(None),
            )
        )
    ).all()
    filtered_games = []
    for game in games:
        d = game.to_dict()
        ai_pred = d.get('ai_predictions')
        exact_result, win_result = calculate_prediction_results(
            d.get('team1_score'),
            d.get('team2_score'),
            ai_pred,
            d.get('bo_type'),
        )
        filtered_games.append({
            "id": d.get('id'),
            "slug": d.get('slug'),
            "bo_type": d.get('bo_type'),
            "start_timestamp": d.get('start_timestamp'),
            "team1_slug": d.get('team1_slug'),
            "team2_slug": d.get('team2_slug'),
            "team1_name": d.get('team1_name'),
            "team2_name": d.get('team2_name'),
            "team1_id": game.team1_id,
            "team2_id": game.team2_id,
            "league_slug": d.get('league_slug'),
            "league_id": game.league_id,
            "team1_score": d.get('team1_score'),
            "team2_score": d.get('team2_score'),
            "ai_predictions": ai_pred,
            "exact_result": exact_result,
            "win_result": win_result,
        })
    result = {"games": filtered_games}
    return responseApi(result, 200)
