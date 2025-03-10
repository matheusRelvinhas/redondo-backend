from flask import jsonify

def responseApi(dict: dict, status_code: int = 200):
    return jsonify(dict), status_code