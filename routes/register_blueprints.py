from flask import Flask
from routes.api import login

def register_blueprints(app: Flask):

    app.register_blueprint(login.bp)
