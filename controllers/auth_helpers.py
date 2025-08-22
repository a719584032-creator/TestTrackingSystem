# controllers/auth_helpers.py
from __future__ import annotations
from functools import wraps
from typing import Iterable, Union
from flask import request, g
from utils.response import json_response
from extensions.jwt import decode_token
from repositories.user_repository import UserRepository
from constants.roles import Role

# 类型别名：允许字符串或 Role 枚举
RoleInput = Union[str, Role]


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


def _normalize_role_item(r: RoleInput) -> str:
    """
    单个角色输入规范化：
      - Role.ADMIN -> "admin"
      - " Admin "  -> "admin"
    """
    if isinstance(r, Role):
        return r.value
    if isinstance(r, str):
        return r.strip().lower()
    raise TypeError(f"不支持的角色类型: {type(r)}")


def _collect_roles(role: RoleInput | None = None,
                   roles: Iterable[RoleInput] | None = None) -> set[str]:
    """
    整理 role / roles 参数到一个集合（全部为枚举值字符串）
    允许：
      auth_required(role=Role.ADMIN)
      auth_required(role="admin")
      auth_required(roles=[Role.ADMIN, Role.DEPT_ADMIN])
      auth_required(role=Role.ADMIN, roles=["dept_admin"])
    """
    collected: list[RoleInput] = []
    if role is not None:
        collected.append(role)
    if roles:
        collected.extend(list(roles))
    normalized = {_normalize_role_item(r) for r in collected}
    # 校验是否属于已定义角色
    invalid = normalized - set(Role.values())
    if invalid:
        # 这里抛错属于开发期问题，返回 500 提醒
        # 也可以选择静默忽略或记录日志
        raise ValueError(f"包含未定义角色: {invalid}")
    return normalized


def auth_required(role: RoleInput | None = None,
                  roles: Iterable[RoleInput] | None = None):
    """
    鉴权装饰器：
      - 验证 Authorization: Bearer <token>
      - 解析 token -> user
      - 可选角色授权（AND = 属于其中任意一个即可）

    用法示例：
      @auth_required()                             # 只需登录
      @auth_required(role=Role.ADMIN)              # 单角色（枚举）
      @auth_required(role="admin")                 # 单角色（字符串，兼容旧用法）
      @auth_required(roles=[Role.ADMIN, Role.DEPT_ADMIN])
      @auth_required(role=Role.ADMIN, roles=["dept_admin"])  # 混合写法（合并）

    注意：
      - 如果既传 role 又传 roles，会合并（即 OR 关系）。
    """
    try:
        required_roles = _collect_roles(role=role, roles=roles)
    except ValueError as e:
        def decorator_error(fn):
            @wraps(fn)
            def wrapper(*_a, **_kw):
                return json_response(code=500, message=f"角色配置错误: {e}")

            return wrapper

        return decorator_error

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = _extract_bearer(request.headers.get("Authorization"))
            if not token:
                return json_response(code=401, message="缺少或无效 Authorization")
            try:
                user = _resolve_user_from_token(token)
            except ValueError as ve:
                code, msg = ve.args[0] if isinstance(ve.args[0], tuple) else ("TOKEN_ERROR", "认证失败")
                return json_response(code=401, message=msg)

            g.current_user = user

            if required_roles and user.role not in required_roles:
                return json_response(code=403, message="权限不足")

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
                return fn(*args, **kwargs)
            try:
                user = _resolve_user_from_token(token)
            except ValueError as ve:
                _code, msg = ve.args[0] if isinstance(ve.args[0], tuple) else ("TOKEN_ERROR", "认证失败")
                return json_response(code=401, message=msg)
            g.current_user = user
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# 可选：额外的纯授权装饰器（需要先有 g.current_user）
def require_roles(*roles: RoleInput):
    """
    仅角色检查，不做 token 解析。适合与 @auth_required() 组合使用：
      @auth_required()
      @require_roles(Role.ADMIN, Role.DEPT_ADMIN)
      def handler(): ...
    """
    roles_set = _collect_roles(roles=roles)

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if not user:
                return json_response(code=401, message="未登录")
            if user.role not in roles_set:
                return json_response(code=403, message="权限不足")
            return fn(*args, **kwargs)

        return wrapper

    return decorator
