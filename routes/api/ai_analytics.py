import json
import os
from flask import Blueprint, request, current_app
from models import db, PlayerStatsLastMonth, PlayerStats3Months, PlayerStats6Months, PlayerStats12Months, AiAnalytics
from routes.api.player_stats import player_info
from routes.api.teams_stats import get_team_games_info
from routes.api.games_stats import game_info_stat
from openai import OpenAI
from utils import responseApi, token_service_required, get_access_and_user
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

bp = Blueprint('ai_analytics', __name__, url_prefix='/api/ai_analytics')

def get_player_ai_anlytics(player_slug):
    model_map = {
        '1': PlayerStatsLastMonth,
        '3': PlayerStats3Months,
        '6': PlayerStats6Months,
        '12': PlayerStats12Months
    }
    player = player_info(model_map, player_slug)
    if player['slug'] != player_slug: return None
    stats_keys = [
        'avg_kills', 'avg_death', 'avg_damage',
        'avg_assists', 'avg_ak47_kills', 'avg_ak47_damage', 'avg_awp_kills', 
        'avg_awp_damage', 'avg_m4a1_kills', 'avg_m4a1_damage',
        'avg_m4a4_kills', 'avg_m4a4_damage', 
    ]
    filtered_stats = []
    for stat in player["stats"]:
        filtered_stat = {key: stat.get(key) for key in stats_keys}
        if stat.get("period") == '1': perido_name = 'last_month'
        if stat.get("period") == '3': perido_name = '3_months'
        if stat.get("period") == '6': perido_name = '6_months'
        if stat.get("period") == '12': perido_name = '12_months'
        filtered_stat["period"] = perido_name
        filtered_stats.append(filtered_stat)
    player["stats"] = filtered_stats
    if (player['team_slug']):
        games_info = get_team_games_info(player['team_slug'])
    if games_info['games']:
        recent_games_slugs = [
            game["slug"]
            for game in sorted(games_info['games'], key=lambda x: x["start_timestamp"], reverse=True)[:5]
        ]
        allowed_player_stats_keys = [
            "adr", "death", "kills", "damage", "assists",
            "clutches", "headshots", "multikills",
            "first_death", "first_kills",
            "trade_death", "trade_kills",
            "enemy_team_name"
        ]
        recent_games_with_player = []
        for game_slug in recent_games_slugs:
            game_i_s = game_info_stat(game_slug, 'players_stats')
            if not game_i_s or 'players_stats' not in game_i_s:
                continue
            player_stats = next(
                (p for p in game_i_s['players_stats'] if p.get('slug') == player_slug),
                None
            )
            if player_stats:
                filtered_player_stats = {
                    key: player_stats[key]
                    for key in allowed_player_stats_keys
                    if key in player_stats
                }
                recent_games_with_player.append({
                    "game_slug": game_slug,
                    "player_stats": filtered_player_stats
                })
    return {
        "player_info": player,  
        "games_info_team": games_info['wl_info'],
        "recent_games_stats_player": recent_games_with_player
    }

def generate_player_analysis(player_slug: str):
    client = OpenAI(api_key=current_app.config["OPENAI_API_KEY"])
    data = get_player_ai_anlytics(player_slug)
    if data is None: return None
    player_info = data.get("player_info", {})
    team_info = data.get("games_info_team", {})
    recent_games = data.get("recent_games_stats_player", [])
    stats = player_info.get("stats", [])
    def get_period(period_name):
        return next((s for s in stats if s.get("period") == period_name), {})
    last_month = get_period("last_month")
    three_months = get_period("3_months")
    six_months = get_period("6_months")
    twelve_months = get_period("12_months")
    context_data = {
        "player": {
            "nickname": player_info.get("nickname"),
            "name": f"{player_info.get('first_name')} {player_info.get('last_name')}",
            "team": player_info.get("team_name"),
            "team_rank": player_info.get("team_rank"),
            "country": player_info.get("country_code"),
        },
        "stats": {
            "last_month": last_month,
            "3_months": three_months,
            "6_months": six_months,
            "12_months": twelve_months,
        },
        "team_performance": team_info,
        "recent_games": recent_games
    }
    prompt = f"""
You are a professional CS2 esports analyst.

Your task is to analyze a player based on structured statistical data.

IMPORTANT RULES:
- Always respond in Brazilian Portuguese (pt-BR).
- Be clear, natural, and professional (like an esports analyst from HLTV).
- Do NOT invent any data.
- Keep the response concise (maximum 200 words).

PRIORITY:
- Give MORE weight to:
  1. Last month stats (last_month)
  2. Recent matches (recent_games)
- Use older data (3, 6, 12 months) only for comparison and trend detection.

INTERPRETATION RULES:
- Translate all stat field names into natural language (no underscores).
  Examples:
    - first_kills → first kills
    - trade_kills → trade kills
    - avg_kills → average kills
- When writing in Portuguese, adapt naturally:
    - "first kills" → "primeiras kills"
    - "trade kills" → "kills de troca"
    - "average damage" → "dano médio"

ANALYZE:
- Current form (recent performance)
- Consistency
- Comparison with past performance
- Impact within the team
- Performance trend (improving or declining)

TEAM CONTEXT:
- Consider team performance (win rate and results)
- Relate player performance to team success

DATA:
{json.dumps(context_data)}

OUTPUT:
Write a short analysis (1–2 paragraphs) covering:
- Current form
- Recent consistency
- Performance trend
- Overall impact

Answer:
"""
    response = client.responses.create(
        model="gpt-5-nano",
        input=prompt,
    )
    result = response.output_text

    return result


@bp.route('/player', methods=["GET"])
@token_service_required
def ai_analytics_player():
    get_access_and_user()
    slug = request.args.get('slug')
    not_ai_return = request.args.get('not_ai_return')
    if not slug:
        return responseApi({"error": "missing_arguments"}, 400)
    cache_key = f"ai_analytics_player::{slug}"
    cached = current_app.cache.get(cache_key)
    if cached:
        current_app.limiter.limit("600 per 1 minutes")(lambda: None)()
        return responseApi(cached, 200)
    brasilia_tz = ZoneInfo("America/Sao_Paulo")
    one_week_ago = int((datetime.now(brasilia_tz) - timedelta(days=7)).timestamp())
    player_analytic = (
        db.session.query(AiAnalytics)
        .filter(
            AiAnalytics.slug == slug,
            AiAnalytics.target_type == 'player',
            AiAnalytics.created_at >= one_week_ago
        )
        .order_by(AiAnalytics.created_at.desc())
        .first()
    )
    if not player_analytic:
        if not_ai_return=='ok':
            return responseApi({"not_ai_return": True}, 200)
        result = generate_player_analysis(slug)
        new_analytic = AiAnalytics(
            slug=slug,
            target_type='player',
            pt_text=result,
            finished=False,
        )
        db.session.add(new_analytic)
        db.session.commit()
    else: result = player_analytic.pt_text
    current_app.cache.set(cache_key, {"ai_analytics_player": result}, timeout=60 * 60 * 24)
    return responseApi({"ai_analytics_player": result}, 200)
