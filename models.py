import pytz
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()
brasilia_tz = pytz.timezone('America/Sao_Paulo')

class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=True)
    access_recover_token = db.Column(db.String(255), nullable=True)
    amount_logins = db.Column(db.Integer, nullable=True, default=0)
    created_at = db.Column(db.Integer, default=lambda: int(datetime.now(brasilia_tz).timestamp()), nullable=True)
    updated_at = db.Column(db.Integer, default=lambda: int(datetime.now(brasilia_tz).timestamp()), onupdate=lambda: int(datetime.now(brasilia_tz).timestamp()), nullable=True)
