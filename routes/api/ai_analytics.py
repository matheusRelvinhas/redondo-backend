import threading
import time
import traceback
from flask import Blueprint, request, current_app
from models import db, AiAnalytics, GamesInfo, TeamsInfo
from routes.api.teams_stats import get_team_info, get_team_players_info, get_team_games_info, get_team_maps_info, get_team_leagues_info
from utils import responseApi, token_service_required, get_access_and_user
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from loguru import logger
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

bp = Blueprint('ai_analytics', __name__, url_prefix='/api/ai_analytics')

CS2_MAPS = {
    "de_dust2": "Dust 2", "de_mirage": "Mirage", "de_inferno": "Inferno",
    "de_nuke": "Nuke", "de_overpass": "Overpass", "de_ancient": "Ancient", "de_anubis": "Anubis"
}

def round_floats(data, decimals=2):
    if isinstance(data, dict):
        return {k: (f"{int(round(v))}%" if k == "performance" and isinstance(v, (int, float)) 
                   else round_floats(v, decimals)) for k, v in data.items()}
    elif isinstance(data, list):
        return [round_floats(v, decimals) for v in data]
    elif isinstance(data, float):
        return round(data, decimals)
    return data

def get_performance_class(percentage):
    if isinstance(percentage, str):
        value = int(percentage.rstrip('%'))
    else:
        value = int(percentage)
    if value < 35:
        return 'text-danger'
    elif value < 70:
        return 'text-tr'
    else:
        return 'text-success'

def delete_old_pending_analytics(slug: str, target_type: str):
    two_minutes_ago = int(time.time()) - 120
    old = db.session.query(AiAnalytics).filter(
        AiAnalytics.slug == slug, AiAnalytics.target_type == target_type,
        AiAnalytics.status == 'pending', AiAnalytics.created_at <= two_minutes_ago
    ).all()
    for item in old:
        db.session.delete(item)
    db.session.commit()

def get_team_ai_analytics(team_slug):
    team = get_team_info(team_slug)
    if isinstance(team, tuple) or not team:
        return None
    players_data = get_team_players_info(team.team_id)
    games_info = get_team_games_info(team_slug)
    aggregated_stats = {}
    for period in ["12_months", "6_months", "3_months", "last_month"]:
        period_stats = [p[period] for p in players_data if p.get(period)]
        if period_stats:
            aggregated_stats[period] = {k: round(sum(s.get(k, 0) for s in period_stats) / len(period_stats), 2) 
                                       for k in ['avg_kills', 'avg_death', 'avg_damage', 'avg_assists']}
        else:
            aggregated_stats[period] = {k: 0 for k in ['avg_kills', 'avg_death', 'avg_damage', 'avg_assists']}
    return round_floats({
        "team_info": team.to_dict(),
        "aggregated_stats": aggregated_stats,
        "games_info": games_info['wl_info'],
        "recent_games": sorted(games_info['games'], key=lambda x: x.get("start_timestamp", 0), reverse=True)[:5],
        "all_games": games_info['games']
    }, 2)

def format_intro(name, rank, country, region=None):
    name = name or "Equipe"
    return (f"{name} é uma equipe profissional de Counter-Strike do país {country} "
            f"(região {region}), atualmente ocupando a posição #{rank} no ranking mundial."
            if region else 
            f"{name} ({country}) é um jogador profissional de Counter-Strike, "
            f"atualmente na posição #{rank} no ranking mundial.")

def format_stats(stats, is_team=False):
    period_labels = {"last_month": "no último mês", "3_months": "nos últimos 3 meses", 
                     "6_months": "nos últimos 6 meses", "12_months": "nos últimos 12 meses"}
    if not is_team:
        return " ".join([f"{period_labels.get(period, period)}, o jogador apresenta em média "
                        f"{data.get('avg_kills', 0)} kills por round, {data.get('avg_death', 0)} mortes, "
                        f"{data.get('avg_damage', 0)} de dano (ADR)" for period, data in stats.items() if period in period_labels])
    
    text_6m = stats.get('6_months', {})
    return f"Nos últimos 6 meses, em média a equipe apresenta {text_6m.get('avg_kills', 0)} kills por round, {text_6m.get('avg_death', 0)} mortes por round, {text_6m.get('avg_damage', 0)} de ADR e {text_6m.get('avg_assists', 0)} assistências por round."

def format_performance(perf, only_6m=False):
    period_labels = {"last_month": "Último mês", "3_months": "Últimos 3 meses",
                     "6_months": "Últimos 6 meses", "12_months": "Últimos 12 meses"}
    
    if only_6m:
        data = perf.get('6_months', {})
        perf_value = data.get('performance', 'N/A')
        perf_class = get_performance_class(perf_value)
        perf_html = f"<strong class='{perf_class}'>{perf_value}</strong>" if perf_value != 'N/A' else perf_value
        return f"Nos últimos 6 meses, {data.get('win', 0)}V-{data.get('lose', 0)}D ({perf_html} desempenho)"
    
    period_order = ["last_month", "3_months", "6_months", "12_months"]
    result = []
    for p in period_order:
        if p in perf:
            data = perf.get(p, {})
            perf_value = data.get('performance', 'N/A')
            perf_class = get_performance_class(perf_value)
            perf_html = f"<strong class='{perf_class}'>{perf_value}</strong>" if perf_value != 'N/A' else perf_value
            result.append(f"<p><strong>{period_labels.get(p, p)}:</strong> {data.get('win', 0)}V-{data.get('lose', 0)}D ({perf_html} desempenho)</p>")
    return "".join(result)

def format_maps(games, team_slug, only_6m=False):
    if not games:
        return "Sem dados de mapa."
    maps_info = get_team_maps_info(games)
    if not maps_info:
        return "Sem dados de mapa."
    now = time.time()
    periods = {"6_months": 182*24*60*60, "12_months": 365*24*60*60} if only_6m else {
        "last_month": 30*24*60*60, "3_months": 91*24*60*60, "6_months": 182*24*60*60, "12_months": 365*24*60*60
    }
    map_stats = {p: {} for p in periods}
    for map_data in maps_info:
        map_code = map_data.get('map_name')
        if map_code not in CS2_MAPS or (map_data.get('team1_slug') != team_slug and map_data.get('team2_slug') != team_slug):
            continue
        map_name = CS2_MAPS[map_code]
        timestamp = map_data.get('start_timestamp', 0)
        won = map_data.get('winner_team') == team_slug
        for period, seconds in periods.items():
            if timestamp >= now - seconds:
                if map_name not in map_stats[period]:
                    map_stats[period][map_name] = {'wins': 0, 'losses': 0}
                map_stats[period][map_name]['wins' if won else 'losses'] += 1
    def build_maps_text(period_maps):
        played = []
        rare = []
        never = []
        for name in CS2_MAPS.values():
            if name in period_maps:
                total = period_maps[name]['wins'] + period_maps[name]['losses']
                if total >= 3:
                    wr = round(period_maps[name]['wins'] / total * 100)
                    wr_class = get_performance_class(wr)
                    wr_html = f"<strong class='{wr_class}'>{wr}%</strong>"
                    played.append(f"<li><strong>{name}</strong>: {period_maps[name]['wins']}V-{period_maps[name]['losses']}D ({wr_html} em {total} mapas)</li>")
                else:
                    rare.append(f"{name} ({total})")
            else:
                never.append(name)
        result = []
        if played:
            result.append(f"<ul>{''.join(played)}</ul>")
        veto_items = []
        if rare:
            veto_items.append(f"<li><strong>Raramente:</strong> {', '.join(rare)}</li>")
        if never:
            veto_items.append(f"<li><strong>Veto fixo ou não jogado:</strong> {', '.join(never)}</li>")
        if veto_items:
            result.append(f"<ul>{''.join(veto_items)}</ul>")
        return "".join(result) if result else "Sem dados de mapas"
    if only_6m:
        maps = map_stats.get('6_months', {})
        return build_maps_text(maps)
    period_pt = {"last_month": "Último mês", "3_months": "Últimos 3 meses", "6_months": "Últimos 6 meses", "12_months": "Últimos 12 meses"}
    result = []
    for p in ["last_month", "3_months", "6_months", "12_months"]:
        maps = map_stats.get(p)
        if not maps:
            continue
        played_only = []
        for name in CS2_MAPS.values():
            if (s := maps.get(name)) and (s['wins'] + s['losses']) > 0:
                wr_percent = round(s['wins']/(s['wins']+s['losses'])*100)
                wr_class = get_performance_class(wr_percent)
                wr_html = f"<strong class='{wr_class}'>{wr_percent}%</strong>"
                played_only.append(f"<li><strong>{name}</strong>: {s['wins']}V-{s['losses']}D ({wr_html} em {s['wins']+s['losses']} mapas)</li>")
        if p in ["6_months", "12_months"]:
            text = f"<p><strong>{period_pt.get(p, p)}:</strong></p>" + build_maps_text(maps)
        else:
            text = (f"<p><strong>{period_pt.get(p, p)}:</strong></p><ul>{''.join(played_only)}</ul>" if played_only else "")
        if text:
            result.append(text)
    return "".join(result) if result else "Sem dados de mapas"

def format_leagues(team_slug):
    leagues = get_team_leagues_info(team_slug)
    if not leagues:
        return "<p>O time não participou de ligas no período.</p>"
    recent = sorted(leagues, key=lambda x: x.get('start_timestamp', 0), reverse=True)[:5]
    items = []
    for l in recent:
        league_name = l.get('name', 'Liga')
        status = l.get('status', 'finished')
        if status == 'current':
            items.append(f"<li>{league_name} (Em Andamento)</li>")
        elif status == 'finished':
            team_place = None
            prizes = l.get('tournament_prizes', [])
            if isinstance(prizes, list):
                for prize in prizes:
                    if isinstance(prize, dict):
                        teams_data = prize.get('teams', {})
                        if isinstance(teams_data, dict) and teams_data.get('slug') == team_slug:
                            team_place = prize.get('place')
                            break
            if team_place:
                if team_place == '1st': items.append(f"<li><strong>{league_name} - {team_place} lugar 🏆</strong></li>")
                else: items.append(f"<li>{league_name} - {team_place} lugar</li>")
            else: items.append(f"<li>{league_name}</li>")
        else: items.append(f"<li>{league_name}</li>")
    return f"<ul>{''.join(items)}</ul>"

def format_recent_games(games, team_slug=None, for_llm=False):
    if not games:
        return "Sem jogos recentes." if for_llm else "<p>Sem jogos recentes.</p>"
    if for_llm:
        wins = sum(1 for g in games if (g.get('team1_slug') == team_slug and g.get('team1_score', 0) > g.get('team2_score', 0)) 
                  or (g.get('team2_slug') == team_slug and g.get('team2_score', 0) > g.get('team1_score', 0)))
        return f"Últimos {len(games)} jogos: {wins}V-{len(games)-wins}D ({round(wins/len(games)*100 if games else 0)}% aproveitamento)"
    items = []
    for g in games:
        is_team1 = g.get('team1_slug') == team_slug
        opponent = g.get('team2_name' if is_team1 else 'team1_name', 'Oponente')
        t_score = g.get('team1_score' if is_team1 else 'team2_score', 0)
        opp_score = g.get('team2_score' if is_team1 else 'team1_score', 0)
        result = "VITÓRIA" if t_score > opp_score else "DERROTA"
        color = "success" if result == "VITÓRIA" else "danger"
        items.append(f"<li>Vs {opponent}: <strong>{t_score}x{opp_score}</strong> - <strong class='text-{color}'>{result}</strong></li>")
    wins = sum(1 for i in items if "VITÓRIA" in i)
    return (f"<ul>{''.join(items)}</ul><p>Últimos 5 jogos: <strong>{wins}V - {len(items)-wins}D</strong> "
            f"(Desempenho: <strong class='{get_performance_class(wins/len(items)*100 if items else 0)}'>{round(wins/len(items)*100)}%</strong>)</p>")

def extract_map_categories_6m(maps_dict):
    veto_fixo = []
    raramente = []
    bem_estabelecidos = []
    for map_name, stats in maps_dict.items():
        total = stats['total']
        if total == 0:
            veto_fixo.append(map_name)
        elif 1 <= total <= 2:
            raramente.append((map_name, total))
        else:
            bem_estabelecidos.append(map_name)
    return {
        'veto_fixo': veto_fixo,
        'raramente': raramente,
        'bem_estabelecidos': bem_estabelecidos
    }

def format_last_clashes_analysis(clashes_data, team1, team2):
    games = clashes_data.get('games', 0)
    team1_wins = clashes_data.get('team1_wins', 0)
    team2_wins = clashes_data.get('team2_wins', 0)
    if games == 0:
        return "<p>Sem histórico de confrontos diretos entre essas equipes.</p>"
    team1_wr = round(team1_wins / games * 100) if games > 0 else 0
    team2_wr = round(team2_wins / games * 100) if games > 0 else 0
    team1_wr_class = get_performance_class(team1_wr)
    team2_wr_class = get_performance_class(team2_wr)
    result_parts = []
    result_parts.append("\n<p><strong>Histórico de Confrontos Diretos (últimos 5 jogos):</strong><br>")
    result_parts.append(f"Confrontos diretos: <strong>{games}</strong> jogos | <strong>{team1['name']}</strong> <strong class='{team1_wr_class}'>{team1_wins}V ({team1_wr}%)</strong> vs <strong>{team2['name']}</strong> <strong class='{team2_wr_class}'>{team2_wins}V ({team2_wr}%)</strong></p>")
    return "".join(result_parts)

def format_maps_analysis(team1, team2, map_comparison, for_llm=False):
    if for_llm:
        team1_analyzed_maps = [(name, stats) for name, stats in team1['maps'].items() if stats['total'] >= 5]
        team2_analyzed_maps = [(name, stats) for name, stats in team2['maps'].items() if stats['total'] >= 5]
        team1_best_map = max(team1_analyzed_maps, key=lambda x: x[1]['winrate']) if team1_analyzed_maps else None
        team2_best_map = max(team2_analyzed_maps, key=lambda x: x[1]['winrate']) if team2_analyzed_maps else None
        analysis_text = f"\nAnálise de Mapas (últimos 6 meses): "
        if team1_best_map:
            analysis_text += f"{team1['name']} é forte em {team1_best_map[0]} ({team1_best_map[1]['winrate']}% em {team1_best_map[1]['total']} jogos). "
        if team2_best_map:
            analysis_text += f"{team2['name']} é forte em {team2_best_map[0]} ({team2_best_map[1]['winrate']}% em {team2_best_map[1]['total']} jogos). "
        critical_analysis = []
        for map_name, comparison in map_comparison.items():
            t1 = comparison['team1']
            t2 = comparison['team2']
            if t1['total'] == 0 or t2['total'] == 0:
                continue
            t1_wr = t1['winrate']
            t2_wr = t2['winrate']
            diff = abs(t1_wr - t2_wr)
            if diff >= 15:
                advantage_team = team1['name'] if t1_wr > t2_wr else team2['name']
                critical_analysis.append((map_name, advantage_team, diff))
        if critical_analysis:
            analysis_text += "Mapas críticos: "
            for map_name, team, diff in critical_analysis[:3]:
                if 1 <= diff <= 15:
                    favoritismo = "baixo favoritismo"
                elif 16 <= diff <= 30:
                    favoritismo = "médio favoritismo"
                elif diff > 30:
                    favoritismo = "alto favoritismo"
                else:
                    favoritismo = "baixo favoritismo"
                analysis_text += f"{map_name} favorece {team} ({favoritismo}). "
        return analysis_text
    else:
        team1_analyzed_maps = [(name, stats) for name, stats in team1['maps'].items() if stats['total'] >= 5]
        team2_analyzed_maps = [(name, stats) for name, stats in team2['maps'].items() if stats['total'] >= 5]
        team1_best_map = max(team1_analyzed_maps, key=lambda x: x[1]['winrate']) if team1_analyzed_maps else None
        team2_best_map = max(team2_analyzed_maps, key=lambda x: x[1]['winrate']) if team2_analyzed_maps else None
        team1_categories = extract_map_categories_6m(team1['maps'])
        team2_categories = extract_map_categories_6m(team2['maps'])
        result_parts = []
        result_parts.append("\n<p><strong>Análise de Mapas (últimos 6 meses):</strong></p>")
        maps_info = []
        team1_info_text = f"<strong>{team1['name']}</strong>"
        if team1_best_map:
            team1_info_text += f" - Melhor mapa: <strong>{team1_best_map[0]}</strong> ({team1_best_map[1]['winrate']}% em {team1_best_map[1]['total']} jogos)"
        team1_info_text += "<br>"
        if team1_categories['veto_fixo']:
            team1_info_text += f"<em>Veto fixo ou não jogado:</em> {', '.join(team1_categories['veto_fixo'])}<br>"
        if team1_categories['raramente']:
            rare_str = ', '.join([f"{name} ({total})" for name, total in team1_categories['raramente']])
            team1_info_text += f"<em>Raramente:</em> {rare_str}"
        maps_info.append(f"<li>{team1_info_text}</li>")
        team2_info_text = f"<strong>{team2['name']}</strong>"
        if team2_best_map:
            team2_info_text += f" - Melhor mapa: <strong>{team2_best_map[0]}</strong> ({team2_best_map[1]['winrate']}% em {team2_best_map[1]['total']} jogos)"
        team2_info_text += "<br>"
        if team2_categories['veto_fixo']:
            team2_info_text += f"<em>Veto fixo ou não jogado:</em> {', '.join(team2_categories['veto_fixo'])}<br>"
        if team2_categories['raramente']:
            rare_str = ', '.join([f"{name} ({total})" for name, total in team2_categories['raramente']])
            team2_info_text += f"<em>Raramente:</em> {rare_str}"
        maps_info.append(f"<li>{team2_info_text}</li>")
        result_parts.append(f"<ul>{''.join(maps_info)}</ul>")
        result_parts.append("\n<p><strong>Mapas Críticos (análise comparativa):</strong></p>")
        critical_analysis = []
        for map_name, comparison in map_comparison.items():
            t1 = comparison['team1']
            t2 = comparison['team2']
            if t1['total'] == 0 or t2['total'] == 0:
                continue
            t1_wr = t1['winrate']
            t2_wr = t2['winrate']
            diff = abs(t1_wr - t2_wr)
            confidence_factor = min(1.0, (t1['total'] + t2['total']) / 20.0)
            criticality = diff * confidence_factor
            advantage_team = team1['name'] if t1_wr > t2_wr else team2['name']
            critical_analysis.append({
                'map': map_name,
                'diff': diff,
                'criticality': criticality,
                'advantage': advantage_team,
                't1': t1,
                't2': t2
            })
        critical_dict = {c['map']: c for c in critical_analysis}
        critical_items = []
        for map_name in CS2_MAPS.values():
            if map_name in critical_dict:
                critical = critical_dict[map_name]
                diff = critical['diff']
                if 1 <= diff <= 15:
                    favoritismo = "baixo favoritismo"
                    fav_class = "text-danger"
                elif 16 <= diff <= 30:
                    favoritismo = "médio favoritismo"
                    fav_class = "text-tr"
                elif diff > 30:
                    favoritismo = "alto favoritismo"
                    fav_class = "text-success"
                else:
                    favoritismo = "baixo favoritismo"
                    fav_class = "text-danger"
                critical_items.append(f"<li><strong>{critical['map']}</strong>: {critical['advantage']} favorito (<strong class='{fav_class}'>{favoritismo}</strong>)</li>")
        result_parts.append(f"<ul>{''.join(critical_items)}</ul>" if critical_items else "<p>Todos os mapas têm distribuição equilibrada.</p>")
        result_parts.append("\n<p><strong>Desempenho em Mapas:</strong></p>")
        map_items = []
        for map_name in CS2_MAPS.values():
            if map_name not in map_comparison:
                continue
            comparison = map_comparison[map_name]
            t1 = comparison['team1']
            t2 = comparison['team2']
            if t1['total'] == 0 or t2['total'] == 0:
                continue
            t1_wr_class = get_performance_class(t1['winrate'])
            t2_wr_class = get_performance_class(t2['winrate'])
            map_items.append(f"<li><strong>{map_name}</strong>: {team1['name']} <strong class='{t1_wr_class}'>{t1['winrate']}%</strong> ({t1['wins']}V-{t1['losses']}D) vs {team2['name']} <strong class='{t2_wr_class}'>{t2['winrate']}%</strong> ({t2['wins']}V-{t2['losses']}D)</li>")
        result_parts.append(f"<ul>{''.join(map_items)}</ul>" if map_items else "<p>Sem mapas em comum.</p>")
        return "".join(result_parts)

def extract_maps_data_6m(games, team_slug):
    if not games:
        return {}
    maps_info = get_team_maps_info(games)
    if not maps_info:
        return {}
    now = time.time()
    six_months_ago = now - (182 * 24 * 60 * 60)
    map_stats = {map_name: {'wins': 0, 'losses': 0} for map_name in CS2_MAPS.values()}
    for map_data in maps_info:
        map_code = map_data.get('map_name')
        if map_code not in CS2_MAPS:
            continue
        if map_data.get('team1_slug') != team_slug and map_data.get('team2_slug') != team_slug:
            continue
        timestamp = map_data.get('start_timestamp', 0)
        if timestamp < six_months_ago:
            continue 
        map_name = CS2_MAPS[map_code]
        won = map_data.get('winner_team') == team_slug
        if won:
            map_stats[map_name]['wins'] += 1
        else:
            map_stats[map_name]['losses'] += 1
    result = {}
    for map_name, stats in map_stats.items():
        total = stats['wins'] + stats['losses']
        wr = round(stats['wins'] / total * 100) if total > 0 else 0
        result[map_name] = {
            'wins': stats['wins'],
            'losses': stats['losses'],
            'total': total,
            'winrate': wr
        }
    return result

def get_last_games_clashes(team1, team2, limit=5):
    clashes = db.session.query(GamesInfo).filter(
        ((GamesInfo.team1_id == team1.team_id) & (GamesInfo.team2_id == team2.team_id)) |
        ((GamesInfo.team1_id == team2.team_id) & (GamesInfo.team2_id == team1.team_id))
    ).filter(
        GamesInfo.status == 'finished'
    ).order_by(GamesInfo.start_date.desc()).limit(limit).all()
    clashes_list = [g.to_dict() for g in clashes]
    team1_wins = 0
    team2_wins = 0
    for clash in clashes_list:
        winner = clash.get('winner_team_slug')
        if winner == team1.slug:
            team1_wins += 1
        elif winner == team2.slug:
            team2_wins += 1
    return {
        'games': len(clashes_list),
        'team1_wins': team1_wins,
        'team2_wins': team2_wins,
        'clashes': clashes_list
    }

def get_game_ai_analytics(game_slug):
    game = db.session.query(GamesInfo).filter(GamesInfo.slug == game_slug).first()
    if not game or (game.status != 'upcoming' and game.status != 'current'):
        return None
    team1 = db.session.query(TeamsInfo).filter(TeamsInfo.team_id == game.team1_id).first()
    team2 = db.session.query(TeamsInfo).filter(TeamsInfo.team_id == game.team2_id).first()
    if not team1 or not team2:
        return None
    team1_slug = team1.slug
    team2_slug = team2.slug
    last_games_team1 = db.session.query(GamesInfo).filter(
        ((GamesInfo.team1_id == game.team1_id) | (GamesInfo.team2_id == game.team1_id))
    ).limit(10).all()
    last_games_team2 = db.session.query(GamesInfo).filter(
        ((GamesInfo.team1_id == game.team2_id) | (GamesInfo.team2_id == game.team2_id))
    ).limit(10).all()
    if (len(last_games_team1) < 3 or len(last_games_team2) < 3):
        return None
    team1_data = get_team_ai_analytics(team1_slug)
    team2_data = get_team_ai_analytics(team2_slug)
    if not team1_data or not team2_data:
        return None
    team1_maps = extract_maps_data_6m(team1_data.get("all_games", []), team1_slug)
    team2_maps = extract_maps_data_6m(team2_data.get("all_games", []), team2_slug)
    map_comparison = {}
    for map_name in CS2_MAPS.values():
        t1_data = team1_maps.get(map_name, {'wins': 0, 'losses': 0, 'total': 0, 'winrate': 0})
        t2_data = team2_maps.get(map_name, {'wins': 0, 'losses': 0, 'total': 0, 'winrate': 0})
        map_comparison[map_name] = {
            'team1': t1_data,
            'team2': t2_data,
            'advantage': 'team1' if t1_data['winrate'] > t2_data['winrate'] else ('team2' if t2_data['winrate'] > t1_data['winrate'] else 'neutral'),
            'winrate_diff': abs(t1_data['winrate'] - t2_data['winrate'])
        }
    team1_perf_6m = team1_data.get('games_info', {}).get('6_months', {})
    team2_perf_6m = team2_data.get('games_info', {}).get('6_months', {})
    team1_stats_6m = team1_data.get('aggregated_stats', {}).get('6_months', {})
    team2_stats_6m = team2_data.get('aggregated_stats', {}).get('6_months', {})
    team1_recent = team1_data.get('recent_games', [])
    team2_recent = team2_data.get('recent_games', [])
    last_clashes = get_last_games_clashes(team1, team2)
    return {
        'game_info': {
            'slug': game_slug,
            'status': game.status,
            'bo_type': game.bo_type,
            'tier': game.tier,
            'start_date': game.start_date,
            'ai_predictions': game.ai_predictions
        },
        'team1': {
            'slug': team1_slug,
            'name': team1.team_name,
            'rank': team1.rank,
            'country': team1.country_code,
            'region': team1.region_code,
            'maps': team1_maps,
            'performance_6m': team1_perf_6m,
            'stats_6m': team1_stats_6m,
            'recent_games': team1_recent
        },
        'team2': {
            'slug': team2_slug,
            'name': team2.team_name,
            'rank': team2.rank,
            'country': team2.country_code,
            'region': team2.region_code,
            'maps': team2_maps,
            'performance_6m': team2_perf_6m,
            'stats_6m': team2_stats_6m,
            'recent_games': team2_recent
        },
        'map_comparison': map_comparison,
        'last_clashes': last_clashes
    }

def generate_text_analysis(response, team1, team2, map_comparison, clashes_data=None):
    result_parts = []
    result_parts.append(response.content.strip())
    result_parts.append("\n<p><strong>Análise de Jogos (últimos 6 meses):</strong></p>")
    team1_perf_html = format_performance({'6_months': team1['performance_6m']}, only_6m=True)
    team1_recent_html = format_recent_games(team1['recent_games'], team1['slug'], for_llm=False)
    team2_perf_html = format_performance({'6_months': team2['performance_6m']}, only_6m=True)
    team2_recent_html = format_recent_games(team2['recent_games'], team2['slug'], for_llm=False)
    perf_items = []
    perf_items.append(f"<li><strong>{team1['name']}</strong><br>{team1_perf_html}<br>{team1_recent_html}</li>")
    perf_items.append(f"<li><strong>{team2['name']}</strong><br>{team2_perf_html}<br>{team2_recent_html}</li>")
    result_parts.append(f"<ul>{''.join(perf_items)}</ul>")
    if clashes_data and clashes_data.get('games', 0) > 0:
        clashes_analysis_html = format_last_clashes_analysis(clashes_data, team1, team2)
        result_parts.append(clashes_analysis_html)
    maps_analysis_html = format_maps_analysis(team1, team2, map_comparison, for_llm=False)
    result_parts.append(maps_analysis_html)
    result = "".join(result_parts)
    return result

def generate_team_analysis(app, analysis_id: int, team_slug: str):
    with app.app_context():
        try:
            data = get_team_ai_analytics(team_slug)
            if not data or len(data.get("recent_games")) == 0:
                team_analytic = db.session.query(AiAnalytics).filter(AiAnalytics.id == analysis_id).first()
                if team_analytic:
                    team_analytic.pt_text = "Sem dados suficientes para análise."
                    team_analytic.status = 'success'
                    db.session.commit()
                return
            team_info = data.get("team_info", {})
            if not isinstance(team_info, dict) and hasattr(team_info, 'to_dict'):
                team_info = team_info.to_dict()
            maps_6m = format_maps(data.get("all_games", []), team_slug, True)
            leagues = format_leagues(team_slug)     
            prompt = PromptTemplate.from_template("""
You are a professional CS2(Counter Strike 2) esports analyst writing a human expert analysis (not structured with numbers).
Write organic, flowing text about the team's positioning and recent form. Focus on last 6 months.
RULES: Brazilian Portuguese only, valid HTML tags only (<p>,<strong>,<br>), max ~100 words, 2 paragraphs, no invented data, NO NUMBERED LISTS.
Use <strong> tags to highlight: team name, key statistics, relevant performance data, and important achievements.
Write as an expert would: discuss team positioning, current form, performance trends, and map strengths naturally.
DATA: Team: {team} | Stats: {stats} | Performance: {performance} | Top Maps: {maps} | Active Leagues: {leagues} | Recent Form: {recent}""")
            chain = prompt | ChatOpenAI(model="gpt-4o-mini", api_key=current_app.config["OPENAI_API_KEY"])
            team_name = team_info.get("name") or team_info.get("team_name") or ""
            response = chain.invoke({
                "team": format_intro(team_name, team_info.get("rank", ""), team_info.get("country_code", ""), team_info.get("region_code", "")),
                "stats": format_stats(data.get("aggregated_stats", {}), is_team=True),
                "performance": format_performance(data.get("games_info", {}), only_6m=True),
                "maps": maps_6m,
                "leagues": leagues,
                "recent": format_recent_games(data.get("recent_games", []), team_slug, for_llm=True)
            })
            result = (f"{response.content.strip()}<br><strong>Desempenho por período:</strong><br>"
                     f"{format_performance(data.get('games_info', {}))}<br><strong>Desempenho em mapas:</strong><br>"
                     f"{format_maps(data.get('all_games', []), team_slug)}<br><strong>Ligas:</strong><br>"
                     f"{leagues}<br><strong>Jogos Recentes:</strong><br>{format_recent_games(data.get('recent_games', []), team_slug)}") 
            team_analytic = db.session.query(AiAnalytics).filter(AiAnalytics.id == analysis_id).first()
            if team_analytic:
                team_analytic.pt_text = result
                team_analytic.status = 'success'
                db.session.commit()
        except Exception as e:
            logger.error(f"team analysis error: {e}\n{traceback.format_exc()}")

def parse_ai_prediction_to_probability(prediction_str):
    if not prediction_str or prediction_str is None:
        return None
    try:
        parts = str(prediction_str).split('-')
        if len(parts) != 2:
            return None
        team1_score = int(parts[0])
        team2_score = int(parts[1])

        total_games = team1_score + team2_score
        if total_games == 0:
            return None
        team1_prob = team1_score / total_games
        return team1_prob
    except:
        return None


def calculate_game_prediction(data):
    """
    Calcula a predição do resultado do jogo baseado em algoritmo com pesos.
    
    Pesos:
    - 8% Rank dos times
    - 12% Stats/Performance/Recent games
    - 24% Last clashes (últimos confrontos diretos)
    - 36% Maps Analysis
    - 20% AI Prediction pré-existente (pré-análise do banco)
    
    Retorna string com predição (ex: "2-0", "2-1", "3-1", "0-1")
    """
    team1 = data['team1']
    team2 = data['team2']
    game_info = data['game_info']
    map_comparison = data['map_comparison']
    last_clashes = data.get('last_clashes', {})
    bo_type = game_info.get('bo_type', 3)
    rank1 = team1.get('rank', 999)
    rank2 = team2.get('rank', 999)
    max_rank = max(rank1, rank2, 1)
    rank_score_team1 = (max_rank - rank1) / max_rank if rank1 < 999 else 0.5
    rank_score_team2 = (max_rank - rank2) / max_rank if rank2 < 999 else 0.5
    stats_score_team1 = 0
    stats_score_team2 = 0
    perf1 = team1.get('performance_6m', {})
    perf2 = team2.get('performance_6m', {})
    win_rate1 = perf1.get('performance', '50%')
    win_rate2 = perf2.get('performance', '50%')
    if isinstance(win_rate1, str):
        win_rate1 = int(win_rate1.rstrip('%')) / 100
    else:
        win_rate1 = win_rate1 / 100 if win_rate1 > 1 else win_rate1
    if isinstance(win_rate2, str):
        win_rate2 = int(win_rate2.rstrip('%')) / 100
    else:
        win_rate2 = win_rate2 / 100 if win_rate2 > 1 else win_rate2
    total_wr = win_rate1 + win_rate2 if (win_rate1 + win_rate2) > 0 else 1
    stats_score_team1 = win_rate1 / total_wr if total_wr > 0 else 0.5
    stats_score_team2 = win_rate2 / total_wr if total_wr > 0 else 0.5
    clashes_score_team1 = 0.5
    clashes_score_team2 = 0.5
    if last_clashes.get('games', 0) > 0:
        total_clashes = last_clashes.get('games', 1)
        team1_clash_wins = last_clashes.get('team1_wins', 0)
        team2_clash_wins = last_clashes.get('team2_wins', 0)
        
        if total_clashes > 0:
            clashes_score_team1 = team1_clash_wins / total_clashes
            clashes_score_team2 = team2_clash_wins / total_clashes
    maps_score_team1 = 0
    maps_score_team2 = 0
    map_count = 0
    for map_name, comparison in map_comparison.items():
        t1_wr = comparison.get('team1', {}).get('winrate', 0) or 0
        t2_wr = comparison.get('team2', {}).get('winrate', 0) or 0
        total_map_wr = (t1_wr + t2_wr) if (t1_wr + t2_wr) > 0 else 1
        if total_map_wr > 0:
            maps_score_team1 += t1_wr / total_map_wr
            maps_score_team2 += t2_wr / total_map_wr
            map_count += 1
    if map_count > 0:
        maps_score_team1 /= map_count
        maps_score_team2 /= map_count
    else:
        maps_score_team1 = 0.5
        maps_score_team2 = 0.5
    ai_pred = game_info.get('ai_predictions')
    print(ai_pred)
    ai_pred_prob_team1 = parse_ai_prediction_to_probability(ai_pred)
    if ai_pred_prob_team1 is not None:
        ai_pred_prob_team2 = 1 - ai_pred_prob_team1
        final_score_team1 = (
            rank_score_team1 * 0.08 +
            stats_score_team1 * 0.12 +
            clashes_score_team1 * 0.24 +
            maps_score_team1 * 0.36 +
            ai_pred_prob_team1 * 0.20
        )
        final_score_team2 = (
            rank_score_team2 * 0.08 +
            stats_score_team2 * 0.12 +
            clashes_score_team2 * 0.24 +
            maps_score_team2 * 0.36 +
            ai_pred_prob_team2 * 0.20
        )
    else:
        final_score_team1 = (
            rank_score_team1 * 0.10 +
            stats_score_team1 * 0.15 +
            clashes_score_team1 * 0.30 +
            maps_score_team1 * 0.45
        )
        final_score_team2 = (
            rank_score_team2 * 0.10 +
            stats_score_team2 * 0.15 +
            clashes_score_team2 * 0.30 +
            maps_score_team2 * 0.45
        )
    total_score = final_score_team1 + final_score_team2 if (final_score_team1 + final_score_team2) > 0 else 1
    team1_probability = final_score_team1 / total_score if total_score > 0 else 0.5
    if bo_type == 1:
        return "1-0" if team1_probability >= 0.5 else "0-1"

    elif bo_type == 3:
        if team1_probability >= 0.65:
            return "2-0"
        elif team1_probability >= 0.5:
            return "2-1"
        elif team1_probability >= 0.35:
            return "1-2"
        else:
            return "0-2"
    elif bo_type == 5:
        if team1_probability >= 0.7:
            return "3-0"
        elif team1_probability >= 0.6:
            return "3-1"
        elif team1_probability >= 0.5:
            return "3-2"
        elif team1_probability >= 0.4:
            return "2-3"
        elif team1_probability >= 0.3:
            return "1-3"
        else:
            return "0-3"
    return "2-1" if team1_probability >= 0.5 else "1-2"


def generate_game_analysis(app, analysis_id: int, game_slug: str):
    with app.app_context():
        try:
            data = get_game_ai_analytics(game_slug)
            if not data:
                game_analytic = db.session.query(AiAnalytics).filter(AiAnalytics.id == analysis_id).first()
                if game_analytic:
                    game_analytic.pt_text = "Jogo não possui estatísticas suficientes para análise."
                    game_analytic.status = 'success'
                    db.session.commit()
                return
            team1 = data['team1']
            team2 = data['team2']
            game_info = data['game_info']
            map_comparison = data['map_comparison']
            bo_type = game_info.get('bo_type', 3)
            ai_prediction = calculate_game_prediction(data)
            print(f"rd-{ai_prediction}")
            prompt = PromptTemplate.from_template("""
You are a professional CS2(Counter Strike 2) esports analyst writing a pre-game prediction analysis.
Write organic, flowing text comparing both teams and presenting the predicted match outcome. Focus on last 6 months data.
RULES: Brazilian Portuguese only, ONLY use HTML tags (<p>, <strong>, <br>) - NO MARKDOWN, NO ** OR __, max ~100 words, 2 paragraphs, no invented data, NO NUMBERED LISTS, NO BULLET POINTS.
IMPORTANT: Use ONLY <strong>text</strong> format, NEVER use **text** or __text__ markdown formatting.
Use <strong> tags to highlight: team names, statistics, key differences, and the predicted result.
Write as an expert would: discuss team comparison, map pool differences, recent form, and explain the predicted outcome.
Don't write about the day or date, as the analysis can be done days before the game.
PREDICTED RESULT: {ai_prediction}
DATA: 
Team1: {team1_info}
Team2: {team2_info}
Maps Analysis: {maps_analysis}
Match: BO{bo_type}
""")
            chain = prompt | ChatOpenAI(model="gpt-4o-mini", api_key=current_app.config["OPENAI_API_KEY"])
            print(f"{team1['name']} {ai_prediction} {team2['name']}")
            response = chain.invoke({
                "ai_prediction": f"{team1['name']} {ai_prediction} {team2['name']}",
                "team1_info": format_intro(team1['name'], team1['rank'], team1['country'], team1.get('region')),
                "team2_info": format_intro(team2['name'], team2['rank'], team2['country'], team2.get('region')),
                "maps_analysis": format_maps_analysis(team1, team2, map_comparison, for_llm=True),
                "bo_type": bo_type
            })
            result = generate_text_analysis(response, team1, team2, map_comparison, data.get('last_clashes'))
            game = db.session.query(GamesInfo).filter(GamesInfo.slug == game_slug).first()
            if game and game.redondo_predictions is None:
                game.redondo_predictions = ai_prediction
                db.session.commit()
            game_analytic = db.session.query(AiAnalytics).filter(AiAnalytics.id == analysis_id).first()
            if game_analytic:
                game_analytic.pt_text = result
                game_analytic.status = 'success'
                db.session.commit()
                logger.info(f"Game analysis generated successfully: {game_slug}")
        except Exception as e:
            logger.error(f"game analysis error: {e}\n{traceback.format_exc()}")
            game_analytic = db.session.query(AiAnalytics).filter(AiAnalytics.id == analysis_id).first()
            if game_analytic:
                db.session.delete(game_analytic)
                db.session.commit()

@bp.route('/team', methods=["GET"])
@token_service_required
def ai_analytics_team():
    try:
        get_access_and_user()
        slug = request.args.get('slug')
        if not slug:
            return responseApi({"error": "missing_arguments"}, 400)
        delete_old_pending_analytics(slug, 'team')
        cache_key = f"ai_analytics_team::{slug}"
        cached = current_app.cache.get(cache_key)
        if cached:
            return responseApi(cached, 200)
        brasilia_tz = ZoneInfo("America/Sao_Paulo")
        one_week_ago = int((datetime.now(brasilia_tz) - timedelta(days=7)).timestamp())
        team_analytic = db.session.query(AiAnalytics).filter(
            AiAnalytics.slug == slug, AiAnalytics.target_type == 'team', AiAnalytics.created_at >= one_week_ago
        ).order_by(AiAnalytics.created_at.desc()).first()
        if team_analytic and team_analytic.status == 'pending':
            return responseApi({"ai_analytics_team": None, "status": "pending"}, 200)
        if not team_analytic:
            if request.args.get('not_ai_return') == 'ok':
                return responseApi({"not_ai_return": True}, 200)
            new = AiAnalytics(slug=slug, target_type='team', status='pending')
            db.session.add(new)
            db.session.commit()
            threading.Thread(target=generate_team_analysis, args=(current_app._get_current_object(), new.id, slug)).start()
            return responseApi({"ai_analytics_team": None, "status": "pending"}, 200)
        result = None
        if team_analytic.status == 'success':
            result = team_analytic.pt_text
            current_app.cache.set(cache_key, {"ai_analytics_team": result, "status": "success", "timestamp": team_analytic.updated_at}, timeout=86400)
        return responseApi({"ai_analytics_team": result, "status": team_analytic.status, "timestamp": team_analytic.updated_at}, 200)
    except Exception as e:
        logger.error(f"team endpoint error: {e}\n{traceback.format_exc()}")
        return responseApi({"error": "internal_error"}, 500)
    
@bp.route('/game', methods=["GET"])
@token_service_required
def ai_analytics_game():
    try:
        get_access_and_user()
        slug = request.args.get('slug')
        if not slug:
            return responseApi({"error": "missing_arguments"}, 400)
        delete_old_pending_analytics(slug, 'game')
        cache_key = f"ai_analytics_game::{slug}"
        cached = current_app.cache.get(cache_key)
        if cached:
            return responseApi(cached, 200)
        game_analytic = db.session.query(AiAnalytics).filter(
            AiAnalytics.slug == slug, AiAnalytics.target_type == 'game'
        ).first()
        if game_analytic and game_analytic.status == 'pending':
            return responseApi({"ai_analytics_game": None, "status": "pending"}, 200)
        if not game_analytic:
            if request.args.get('not_ai_return') == 'ok':
                return responseApi({"not_ai_return": True}, 200)
            new = AiAnalytics(slug=slug, target_type='game', status='pending')
            db.session.add(new)
            db.session.commit()
            threading.Thread(target=generate_game_analysis, args=(current_app._get_current_object(), new.id, slug)).start()
            return responseApi({"ai_analytics_game": None, "status": "pending"}, 200)
        result = None
        if game_analytic.status == 'success':
            result = game_analytic.pt_text
            current_app.cache.set(cache_key, {"ai_analytics_game": result, "status": "success", "timestamp": game_analytic.updated_at}, timeout=86400)
        return responseApi({"ai_analytics_game": result, "status": game_analytic.status, "timestamp": game_analytic.updated_at}, 200)
    except Exception as e:
        logger.error(f"game endpoint error: {e}\n{traceback.format_exc()}")
        return responseApi({"error": "internal_error"}, 500)
