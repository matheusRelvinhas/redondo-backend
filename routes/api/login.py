import re
import jwt
import os
import resend
from flask import Blueprint, request, redirect, current_app
from datetime import datetime, timedelta
from email_validator import validate_email, EmailNotValidError
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
from utils import responseApi, get_access_and_user

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
        new_user = User(email=email, password=hashed_password, amount_logins=0)
        db.session.add(new_user)
        db.session.commit()
        token_jwt = generate_jwt_token(new_user.id)
        return responseApi({"message": "user_registered", "user_id": new_user.id, "token": token_jwt}, 200)

    elif login_type == 'login':
        user = User.query.filter_by(email=email).first()
        if not user:
            return responseApi({"error": "user_not_found"}, 400)
        else:
            user.amount_logins += 1
            db.session.commit()
        if not user.password or not check_password_hash(user.password, password):
            return responseApi({"error": "invalid_email_password"}, 400)
        token_jwt = generate_jwt_token(user.id)
        return responseApi({"message": "login_success", "user_id": user.id, "token": token_jwt}, 200)
    return responseApi({"error": "invalid_email_password"}, 400)

@bp.route('/google')
def google_login():
    google = current_app.oauth.create_client('google')
    redirect_uri = f"{os.getenv('BACKEND_URL')}/api/login/google/callback"
    return google.authorize_redirect(redirect_uri)

@bp.route('/google/callback')
def google_callback():
    google = current_app.oauth.create_client('google')
    google.authorize_access_token()
    user_info = google.userinfo()
    email = user_info.get("email")
    name = user_info.get("name")
    if not email:
        return responseApi({"error": "google_login_failed"}, 400)
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, name=name, password=None, amount_logins=0)
        login_type='register'
        db.session.add(user)
    else:
        user.amount_logins += 1
        login_type='login'
    db.session.commit()
    jwt_token = generate_jwt_token(user.id)
    redirect_url = f"{os.getenv('FRONTEND_URL')}/login?login_type={login_type}&token={jwt_token}"
    return redirect(redirect_url)

@bp.route('/logout', methods=["GET"])
def logout():
    token = request.args.get('token')
    get_access_and_user(token)
    return responseApi({"message": "logout_success"}, 200)

@bp.route('/check_auth', methods=["GET"])
def check_auth():
    token = request.args.get('token')
    user = get_access_and_user(token)
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

@bp.route('/recover_password', methods=["GET"])
def recover_password():
    email = request.args.get('email')
    resend.api_key = os.getenv('RESEND_API_KEY')
    user = User.query.filter_by(email=email).first()
    if not user:
        return responseApi({"error": "invalid_email"}, 400)
    recover_token = generate_jwt_token(user.id)
    reset_link = f"{os.getenv('FRONTEND_URL')}/login?recover_token={recover_token}"
    print(reset_link)
    try:
        #response = resend.Emails.send({
        #    "from": "onboarding@resend.dev",
        #    "to": email,
        #    "subject": 'Recuperar senha - Project X',
        #    "html": f"<p>Olá, clique no link abaixo para redefinir sua senha:</p><a href='{reset_link}' target='_blank'>{reset_link}</a>"
        #})
        return responseApi({"message": "email_sent"}, 200)
    except Exception as e:
        print("Erro ao enviar e-mail:", e)
        return responseApi({"error": "error_recover_password"}, 400)

@bp.route('/reset_password', methods=["GET"])
def reset_password():
    recover_token = request.args.get('recover_token')
    new_password = request.args.get("new_password")
    if not recover_token or not new_password or not validate_password(new_password):
        return responseApi({"error": "error_reset_password"}, 400)
    try:
        decoded = jwt.decode(recover_token, os.getenv('JWT_SECRET_KEY'), algorithms=['HS256'])
        user_id = decoded.get("user_id")
    except jwt.ExpiredSignatureError:
        return responseApi({"error": "token_expired"}, 400)
    except jwt.InvalidTokenError:
        return responseApi({"error": "error_reset_password"}, 400)
    user = User.query.get(user_id)
    if not user:
        return responseApi({"error": "error_reset_password"}, 400)
    user.password = generate_password_hash(new_password)
    db.session.commit()
    return responseApi({"message": "password_updated"}, 200)
