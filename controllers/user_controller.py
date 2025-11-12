# controllers/user_controller.py
from flask import Blueprint, request, g
from controllers.auth_helpers import auth_required, require_system_roles
from services.user_service import UserService
from utils.response import json_response
from utils.exceptions import BizError
from constants.roles import SystemRole
import traceback

user_bp = Blueprint("users", __name__)


@user_bp.post("/create")
@auth_required()
@require_system_roles(SystemRole.ADMIN)
def create_user():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    email = data.get("email")
    phone = data.get("phone")
    role_raw = data.get("role")

    if not username or not password:
        return json_response(message="用户名或密码不能为空", code=400)
    user = UserService.create_user(username, password, role_raw, email, phone)
    return json_response(
        message="创建成功",
        data={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
            "role_label": getattr(user, "role_label", user.role),
            "active": user.active
        },
        code=200
    )


@user_bp.get("/list")
@auth_required()
@require_system_roles(SystemRole.ADMIN, SystemRole.OPERATOR)
def list_users():
    """
    GET /users/list
    支持组合查询：
      page, page_size
      username (模糊)
      role (英文，逗号分隔)
      role_label (中文，逗号分隔)
      email (模糊)
      phone (模糊)
      active (true/false/1/0)
      department_id (admin 可任意；dept_admin 必须在其管理范围内)
    """
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))

    username = request.args.get("username")
    email = request.args.get("email")
    phone = request.args.get("phone")

    # role / role_label 多值解析
    def split_multi(val):
        return [v.strip() for v in val.split(",") if v.strip()] if val else None
    roles = split_multi(request.args.get("role"))
    role_labels = split_multi(request.args.get("role_label"))

    # active 解析
    active_raw = request.args.get("active")
    active = None
    if active_raw is not None:
        low = str(active_raw).lower()
        if low in ("1", "true", "t", "yes"):
            active = True
        elif low in ("0", "false", "f", "no"):
            active = False

    department_id = request.args.get("department_id")
    if department_id:
        try:
            department_id = int(department_id)
        except ValueError:
            return json_response(code=400, message="department_id 非法")

    current_user = getattr(g, "current_user", None) or getattr(g, "user", None)
    if not current_user:
        return json_response(code=401, message="未认证")

    items, total, dept_map = UserService.list_users(
        page=page,
        page_size=page_size,
        current_user=current_user,
        username=username,
        roles=roles,
        role_labels=role_labels,
        email=email,
        phone=phone,
        active=active,
        department_id=department_id
    )

    return json_response(
        code=200,
        data={
            "total": total,
            "items": [
                {
                    "id": u.id,
                    "username": u.username,
                    "role": u.role,
                    "role_label": u.role_label,  # property (使用 ROLE_LABELS_ZH)
                    "email": u.email,
                    "phone": u.phone,
                    "active": u.active,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                    "departments": dept_map.get(u.id, [])
                }
                for u in items
            ]
        }
    )


@user_bp.patch("/<int:user_id>/status")
@auth_required()
@require_system_roles(SystemRole.ADMIN)
def change_user_status(user_id: int):
    """
    修改用户 active 状态
    Request JSON: {"active": true/false}
    """
    data = request.get_json(silent=True) or {}
    if "active" not in data:
        return json_response(message="缺少 active 字段", code=400)
    active = data.get("active")
    if not isinstance(active, bool):
        return json_response(message="active 必须为布尔值", code=400)

    actor = getattr(g, "current_user", None)
    if not actor:
        return json_response(message="未授权", code=401)

    user = UserService.update_user_status(actor, user_id, active)
    return json_response(
        message="更新成功",
        data={
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "active": user.active
        },
        code=200
    )


@user_bp.patch("/<int:user_id>/profile")
@auth_required()
@require_system_roles(SystemRole.ADMIN, SystemRole.OPERATOR)
def update_user_profile(user_id: int):
    """
    管理员 / 部门管理员更新指定用户。
    """
    data = request.get_json(silent=True) or {}
    allowed_keys = {"email", "phone", "role"}
    if not (allowed_keys & set(data.keys())):
        return json_response(message="缺少可更新字段", code=400)

    actor = getattr(g, "current_user", None)
    if not actor:
        return json_response(message="未授权", code=401)

    user = UserService.update_user_profile(
        actor=actor,
        target_user_id=user_id,
        email=data.get("email"),
        phone=data.get("phone"),
        role_raw=data.get("role")
    )
    return json_response(
        message="更新成功",
        data={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
            "role_label": getattr(user, "role_label", user.role),
            "active": user.active
        },
        code=200
    )


@user_bp.patch("/me/profile")
@auth_required()  # 任意已登录用户
def update_self_profile():
    """
    用户自身更新邮箱 / 手机号
    """
    actor = getattr(g, "current_user", None)
    if not actor:
        return json_response(message="未授权", code=401)
    data = request.get_json(silent=True) or {}
    if not {"email", "phone"} & set(data.keys()):
        return json_response(message="缺少可更新字段", code=400)

    user = UserService.update_user_profile(
        actor=actor,
        target_user_id=actor.id,
        email=data.get("email"),
        phone=data.get("phone")
    )
    return json_response(
        message="更新成功",
        data={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
            "role_label": getattr(user, "role_label", user.role),
            "active": user.active
        },
        code=200
    )


@user_bp.post("/<int:user_id>/password/reset")
@auth_required()
def reset_user_password(user_id: int):
    """
    重置指定用户密码：
      - 管理员可重置任意用户
      - 其它角色仅可重置自身
    返回新密码明文（仅本次），提示尽快修改。
    """
    actor = getattr(g, "current_user", None)
    if not actor:
        return json_response(message="未授权", code=401)

    user = UserService.reset_password(actor=actor, target_user_id=user_id)

    # 取出一次性明文密码
    new_password = getattr(user, "_plain_reset_password", None)

    # （可选）避免后续逻辑误用，删掉这个属性
    if hasattr(user, "_plain_reset_password"):
        delattr(user, "_plain_reset_password")

    return json_response(
        message="密码已重置，请尽快修改",
        data={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
            "role_label": getattr(user, "role_label", user.role),
            "active": user.active,
            "new_password": new_password
        },
        code=200
    )
