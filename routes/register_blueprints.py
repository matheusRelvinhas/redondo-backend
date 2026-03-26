from flask import Flask
from routes.api import login, player_stats, teams_stats, leagues_stats, games_stats, ai_analytics

def register_blueprints(app: Flask):

    app.register_blueprint(login.bp)

    app.register_blueprint(player_stats.bp)

    app.register_blueprint(teams_stats.bp)

    app.register_blueprint(leagues_stats.bp)

    app.register_blueprint(games_stats.bp)

    app.register_blueprint(ai_analytics.bp)