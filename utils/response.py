from flask import jsonify


def json_response(message="success", data=None, code=200):
    resp = jsonify({"code": code, "message": message, "data": data})
    resp.status_code = code
    return resp

