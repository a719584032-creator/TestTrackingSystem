# middlewares/auth.py
import functools
from flask import request, g
from extensions.jwt import decode_token, TokenError
from utils.response import json_response

def login_required(fn):
    @functools.wraps(fn)
    def _wrap(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return json_response(code=401, message="未授权")
        token = auth.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token)
        except TokenError as e:
            return json_response(code=401, message=str(e))
        g.current_user_id = payload.get("sub")
        g.jwt_payload = payload
        return fn(*args, **kwargs)
    return _wrap
