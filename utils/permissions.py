# utils/permissions.py
from flask import g
from constants.roles import Role
from constants.department_roles import DepartmentRole
from utils.exceptions import BizError


def get_current_user():
    """
    获取当前登录用户（由 auth_required 写入 g.current_user）
    """
    user = getattr(g, "current_user", None)
    if not user:
        raise BizError("未登录", 401)
    return user


def is_global_admin(user=None) -> bool:
    """
    全局管理员判断（你如果将来多加 SUPER_ADMIN，可扩展）
    """
    if user is None:
        user = getattr(g, "current_user", None)
    if not user:
        return False
    return user.role in {Role.ADMIN.value}


def user_is_dept_admin(dept_id: int, user=None) -> bool:
    """
    判断用户是否为指定部门的 dept_admin（或全局 admin）
    """
    if user is None:
        user = getattr(g, "current_user", None)
    if not user:
        return False
    if is_global_admin(user):
        return True
    # 遍历其部门成员记录
    # user.department_memberships 由 DepartmentMember.user backref 提供
    for membership in getattr(user, "department_memberships", []):
        if membership.department_id == dept_id and membership.role == DepartmentRole.ADMIN.value:
            return True
    return False


def assert_dept_admin(dept_id: int, user=None):
    """
    断言当前用户是该部门管理员（或全局管理员），否则抛出 BusinessError
    """
    if not user_is_dept_admin(dept_id, user=user):
        raise BizError("无权限（需要部门管理员或全局管理员）", 403)


def assert_global_admin(user=None):
    if not is_global_admin(user=user):
        raise BizError("需要全局管理员权限", 403)
