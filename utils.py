import os
import jwt
from flask import jsonify, request
from models import User
from functools import wraps

def responseApi(dict: dict, status_code: int = 200):
    return jsonify(dict), status_code

def get_bearer_token():
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    return auth.split("Bearer ")[1]

def get_access_and_user():
    token = get_bearer_token()
    if not token:
        return responseApi({"error": "token_missing"}, 400)
    try:
        payload = jwt.decode(token, os.getenv('JWT_SECRET_KEY'), algorithms=['HS256'])
        user_id = payload.get('user_id')
        user = User.query.filter_by(id=user_id).first()
        if not user: return responseApi({"error": "token_error"}, 400)
        else: return user
    except:
        return responseApi({"error": "token_error"}, 400)

def token_service_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-Service-Token")
        frontend_url = os.getenv("FRONTEND_URL", "").rstrip("/")
        if not token or token != os.getenv("SERVICE_TOKEN"):
            return responseApi({"error": "invalid_service_token"}, 403)
        origin = request.headers.get("Origin", "").rstrip("/")
        referer = request.headers.get("Referer", "")
        origin_valid = origin == frontend_url
        referer_valid = referer.startswith(frontend_url)
        if not origin_valid and not referer_valid:
            return responseApi({"error": "invalid_origin"}, 403)
        return f(*args, **kwargs)
    return decorated