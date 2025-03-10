import re
import jwt
import os
from flask import Blueprint, request
from datetime import datetime, timedelta
from email_validator import validate_email, EmailNotValidError
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
from utils import responseApi

def validate_email_function(email: str) -> bool:
    try:
        validate_email(email)
        return True
    except EmailNotValidError:
        return False

def validate_password(password: str) -> bool:
    regex = r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$'
    return bool(re.match(regex, password))

def generate_jwt_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    encode = jwt.encode(payload, os.getenv('JWT_SECRET_KEY'), algorithm='HS256')
    decode = jwt.decode(encode, os.getenv('JWT_SECRET_KEY'), algorithms=['HS256'])
    print(f"{decode.get('user_id')}")
    return encode

bp = Blueprint('login', __name__, url_prefix='/api/login')
@bp.route('/', methods=["GET"])
def login():
    email = request.args.get('email')
    password = request.args.get('pwd')
    login_type = request.args.get('login_type')

    if not email or not password or not login_type or not validate_email_function(email) or not validate_password(password):
        return responseApi({"error": "invalid_email_password"}, 400)

    if login_type == 'register':
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return responseApi({"error": "user_exists"}, 400)
        hashed_password = generate_password_hash(password)
        new_user = User(email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        token_jwt = generate_jwt_token(new_user.id)
        return responseApi({"message": "user_registered", "user_id": new_user.id, "token": token_jwt}, 200)

    elif login_type == 'login':
        user = User.query.filter_by(email=email).first()
        if not user:
            return responseApi({"error": "user_not_found"}, 400)
        if not check_password_hash(user.password, password):
            return responseApi({"error": "invalid_email_password"}, 400)
        token_jwt = generate_jwt_token(user.id)
        return responseApi({"message": "login_success", "user_id": user.id, "token": token_jwt}, 200)
    return responseApi({"error": "invalid_email_password"}, 400)


@bp.route('/logout', methods=["GET"])
def logout():
    return responseApi({"message": "logout_success"}, 200)

@bp.route('/check_auth', methods=["GET"])
def check_auth():
    token = request.args.get('token')
    if not token:
        return responseApi({"error": "token_missing"}, 400)   
    payload = jwt.decode(token, os.getenv('JWT_SECRET_KEY'), algorithms=['HS256'])
    print(f"{payload.get('user_id')}")
    user_id = payload.get('user_id')
    user = User.query.filter_by(id=user_id).first()
    if user:
        return responseApi(
            {
                "message": "authenticated", 
                "user_id": user.id,
                "name": user.name,
                "email": user.email,
                "logged": True,
                "premium": False 
            }, 200)
    else:
        return responseApi({"error": "user_not_found"}, 400)


