# controllers/auth_controller.py
from controllers.auth_helpers import auth_required
from flask import Blueprint, request, g
from services.user_service import UserService
from services.password_service import PasswordService
from extensions.jwt import create_token, revoke_token
from utils.response import json_response


auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return json_response(code=400, message="用户名密码必填")
    user = UserService.authenticate(username, password)
    print(user)
    if not user:
        return json_response(code=401, message="用户名或密码错误")
    token = create_token(user.id, user.username, user.role, user.password_version)
    return json_response(data={
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "email": user.email
        }
    })


@auth_bp.post("/logout")
def logout():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return json_response(message="已退出登录")
    token = auth.split(" ", 1)[1].strip()
    revoke_token(token)
    return json_response(message="已退出登录")


@auth_bp.post("/change-password")
@auth_required()
def change_password():
    data = request.get_json(silent=True) or {}
    result = PasswordService.change_password(
        user=g.current_user,
        old_password=(data.get("old_password") or "").strip(),
        new_password=(data.get("new_password") or "").strip(),
        confirm_password=(data.get("confirm_password") or "").strip(),
        current_token=_extract_bearer(request.headers.get("Authorization"))
    )
    return json_response(data=result)


def _extract_bearer(auth_header: str | None):
    if not auth_header:
        return None
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return None



