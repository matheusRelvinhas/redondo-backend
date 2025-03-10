import os
import jwt
from flask import jsonify
from models import User

def responseApi(dict: dict, status_code: int = 200):
    return jsonify(dict), status_code

def get_access_and_user(token):
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
