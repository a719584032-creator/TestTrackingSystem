# controllers/auth_helpers.py
from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Union

from flask import g, request

from constants.department_roles import DepartmentRole
from constants.roles import SystemRole
from extensions.jwt import decode_token
from repositories.user_repository import UserRepository
from utils.permissions import (
    PermissionScope,
    build_permission_scope,
    get_permission_scope,
)
from utils.response import json_response


def _extract_bearer(auth_header: str | None) -> str | None:
    if not auth_header:
        return None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        return token or None
    return None


def _resolve_user_from_token(token: str):
    """
    解析 token 并返回 user 对象。
    失败时抛出 (code, message) 的 ValueError，供调用方决定如何返回。
    """
    try:
        payload = decode_token(token)
    except ValueError:
        raise ValueError(("TOKEN_INVALID", "Token 无效或已过期"))

    user_id = payload.get("sub")
    if user_id is None:
        raise ValueError(("TOKEN_PAYLOAD_INVALID", "Token 载荷无效"))
    user = UserRepository.find_by_id(user_id)
    if not user or not getattr(user, "active", False):
        raise ValueError(("USER_NOT_FOUND", "用户不存在或被禁用"))

    token_pwdv = payload.get("pwdv")
    if token_pwdv is None or token_pwdv != user.password_version:
        raise ValueError(("TOKEN_PWD_VERSION_MISMATCH", "登录状态已失效，请重新登录"))

    return user


def _attach_scope(user) -> PermissionScope:
    scope = build_permission_scope(user)
    g.permission_scope = scope
    return scope


def auth_required():
    """
    鉴权装饰器：
      - 验证 Authorization: Bearer <token>
      - 解析 token -> user
      - 构建 PermissionScope，注入 g.permission_scope
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            g.current_user = None
            g.permission_scope = None
            token = _extract_bearer(request.headers.get("Authorization"))
            if not token:
                return json_response(code=401, message="缺少或无效 Authorization")
            try:
                user = _resolve_user_from_token(token)
            except ValueError as ve:
                code, msg = ve.args[0] if isinstance(ve.args[0], tuple) else ("TOKEN_ERROR", "认证失败")
                return json_response(code=401, message=msg)

            g.current_user = user
            _attach_scope(user)

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def optional_auth():
    """
    可选鉴权：
      - 无 Authorization：g.current_user = None，继续
      - 有 Authorization 且有效：注入 g.current_user
      - 有 Authorization 但无效：返回 401
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = _extract_bearer(request.headers.get("Authorization"))
            if token is None:
                g.current_user = None
                g.permission_scope = None
                return fn(*args, **kwargs)
            try:
                user = _resolve_user_from_token(token)
            except ValueError as ve:
                _code, msg = ve.args[0] if isinstance(ve.args[0], tuple) else ("TOKEN_ERROR", "认证失败")
                return json_response(code=401, message=msg)
            g.current_user = user
            _attach_scope(user)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def _normalize_system_role_value(value: SystemRole | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, SystemRole):
        return value.value
    value = value.strip().lower()
    return value or None


def require_system_roles(*roles: SystemRole | str):
    """
    系统级角色校验，依赖于 @auth_required 预先注入的 PermissionScope。
    """
    normalized = {_normalize_system_role_value(role) for role in roles if role}
    if not normalized:
        raise ValueError("require_system_roles 需要至少指定一个系统角色")

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            scope = get_permission_scope()
            if not scope:
                return json_response(code=401, message="未登录")
            if not scope.has_system_role(*normalized):
                return json_response(code=403, message="系统权限不足")
            return fn(*args, **kwargs)

        return wrapper

    return decorator


DeptResolver = Union[int, str, Callable[..., Any], None]


def _resolve_department_id(source: DeptResolver, args, kwargs):
    if callable(source):
        return source(*args, **kwargs)
    if isinstance(source, str):
        if source in kwargs:
            return kwargs[source]
        view_args = getattr(request, "view_args", {}) or {}
        if source in view_args:
            return view_args[source]
        return None
    if source is None:
        for key in ("department_id", "dept_id"):
            if key in kwargs:
                return kwargs[key]
        view_args = getattr(request, "view_args", {}) or {}
        for key in ("department_id", "dept_id"):
            if key in view_args:
                return view_args[key]
        return None
    return source


def require_department_role(
    dept_source: DeptResolver,
    role: DepartmentRole = DepartmentRole.ADMIN,
    *,
    include_system_admin: bool = True,
    error_message: str = "部门权限不足",
):
    """
    校验当前用户在指定部门内是否拥有指定最小角色。
    dept_source 支持：
      - 直接传入部门 ID（int）
      - 形参名（str），会从 kwargs 或 view_args 里取
      - Callable，签名为 f(*args, **kwargs) -> dept_id
      - None：默认尝试 department_id/dept_id
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            scope = get_permission_scope()
            if not scope:
                return json_response(code=401, message="未登录")
            dept_id = _resolve_department_id(dept_source, args, kwargs)
            if dept_id is None:
                return json_response(code=400, message="缺少 department_id")
            if not scope.has_department_role(
                int(dept_id),
                required_role=role,
                include_system_admin=include_system_admin,
            ):
                return json_response(code=403, message=error_message)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
