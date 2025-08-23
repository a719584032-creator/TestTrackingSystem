# controllers/department_controller.py
from flask import Blueprint, request, g
from utils.response import json_response
from utils.exceptions import BizError
from services.department_service import DepartmentService
from repositories.department_member_repository import DepartmentMemberRepository
from services.department_member_service import DepartmentMemberService
from services.user_service import UserService
from utils.permissions import (
    get_current_user,
    assert_dept_admin,
    is_global_admin,
)
from constants.roles import Role
from constants.department_roles import DEPARTMENT_ROLE_SET
from controllers.auth_helpers import auth_required  # 你的鉴权装饰器

department_bp = Blueprint("department", __name__, url_prefix="/api/departments")


@department_bp.errorhandler(BizError)
def _biz_error(e: BizError):
    return json_response(code=e.code, message=e.message), e.code


# 创建部门（仅全局 admin）
@department_bp.post("")
@auth_required(role=Role.ADMIN)
def create_department():
    data = request.get_json(silent=True) or {}
    dept = DepartmentService.create(
        name=data.get("name"),
        code=data.get("code"),
        description=data.get("description"),
    )
    return json_response(message="创建成功", data=dept.to_dict())


# 部门列表（登录即可）
@department_bp.get("")
@auth_required()
def list_departments():
    args = request.args

    # 获取筛选参数
    name = args.get("name", "").strip() or None
    code = args.get("code", "").strip() or None

    # 状态参数处理
    active = None
    active_raw = args.get("active", "").strip()
    if active_raw is not None:
        low = str(active_raw).lower()
        if low in ("1", "true", "t", "yes"):
            active = True
        elif low in ("0", "false", "f", "no"):
            active = False

    # 分页参数
    page = max(int(args.get("page", 1)), 1)
    page_size = min(max(int(args.get("page_size", 20)), 1), 100)

    # 排序参数
    order_desc = args.get("order", "desc").lower() != "asc"

    departments, total, counts_data = DepartmentService.list(
        name=name,
        code=code,
        active=active,
        page=page,
        page_size=page_size,
        order_desc=order_desc
    )

    return json_response(data={
        "items": [d.to_dict(counts_data=counts_data) for d in departments],
        "total": total,
        "page": page,
        "page_size": page_size
    })



# 部门详情
@department_bp.get("/<int:dept_id>")
@auth_required()
def get_department(dept_id: int):
    dept = DepartmentService.get(dept_id)
    # 如果需要限制只有管理员才能看 members，可以做：
    # if with_members and not user_is_dept_admin(dept_id):
    #     raise BusinessError("无权查看成员列表", 403)
    _, _, counts_data = DepartmentService.list()
    return json_response(data=dept.to_dict(counts_data=counts_data))


# 更新部门（部门管理员或全局管理员）
@department_bp.put("/<int:dept_id>")
@auth_required(roles=[Role.ADMIN, Role.DEPT_ADMIN])
def update_department(dept_id: int):
    data = request.get_json(silent=True) or {}
    # 状态参数处理
    active = None
    active_raw = data.get("active", "")
    if active_raw is not None:
        low = str(active_raw).lower()
        if low in ("1", "true", "t", "yes"):
            active = True
        elif low in ("0", "false", "f", "no"):
            active = False
    dept = DepartmentService.update(
        dept_id=dept_id,
        name=data.get("name"),
        code=data.get("code"),
        description=data.get("description"),
        active=active
    )
    return json_response(message="更新成功", data=dept.to_dict())


# 禁用部门（全局管理员）
@department_bp.patch("/<int:dept_id>/status")
@auth_required(role=Role.ADMIN)
def toggle_department_status(dept_id: int):
    """切换部门状态（启用/禁用）"""
    data = request.get_json() or {}
    active = data.get("active")

    if active is None:
        return json_response(message="缺少active参数")

    if not isinstance(active, bool):
        return json_response(message="active参数必须为布尔值")

    DepartmentService.toggle_status(dept_id, active=active)

    action = "启用" if active else "禁用"
    return json_response(message=f"部门{action}成功")


# 添加成员（部门管理员或全局管理员）
@department_bp.post("/<int:dept_id>/members")
@auth_required(roles=[Role.ADMIN, Role.DEPT_ADMIN])
def add_member(dept_id: int):
    user = get_current_user()
    assert_dept_admin(dept_id, user=user)

    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    role = data.get("role", "dept_viewer")
    upsert = bool(data.get("upsert", False))
    if not user_id:
        return json_response(code=400, message="user_id 必填")
    if role not in DEPARTMENT_ROLE_SET:
        return json_response(code=400, message="非法角色")

    member, updated = DepartmentMemberService.add_member(dept_id, user_id, role, upsert=upsert)
    return json_response(
        message="更新成员成功" if updated else "添加成员成功",
        data=member.to_dict()
    )


# 成员列表（默认所有登录用户可看）
@department_bp.get("/<int:dept_id>/members")
@auth_required()
def list_members(dept_id: int):
    # 可选权限限制：
    # if not (user_is_dept_admin(dept_id) or user_in_department(dept_id)):
    #     raise BusinessError("无权查看该部门成员", 403)
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
        department_id=dept_id
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


# 修改成员角色
@department_bp.patch("/role/<int:member_id>")
@auth_required()
def update_member_role(member_id: int):
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    role = data.get("role")
    if not role:
        return json_response(code=400, message="role 必填")
    if role not in DEPARTMENT_ROLE_SET:
        return json_response(code=400, message="非法角色")

    m = DepartmentMemberRepository.get_by_id(member_id)
    if not m:
        return json_response(code=404, message="成员不存在")

    assert_dept_admin(m.department_id, user=user)
    member = DepartmentMemberService.update_member_role(member_id, role)
    return json_response(message="角色修改成功", data=member.to_dict())


# 移除成员
@department_bp.delete("/<int:member_id>")
@auth_required()
def remove_member(member_id: int):
    user = get_current_user()
    m = DepartmentMemberRepository.get_by_id(member_id)
    if not m:
        return json_response(message="已移除(幂等)")
    assert_dept_admin(m.department_id, user=user)
    DepartmentMemberService.remove_member(member_id)
    return json_response(message="移除成功")
