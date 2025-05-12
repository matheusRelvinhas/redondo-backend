from flask import Flask
from routes.api import login, player_stats

def register_blueprints(app: Flask):

    app.register_blueprint(login.bp)

    app.register_blueprint(player_stats.bp)
