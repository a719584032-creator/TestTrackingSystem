from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Sequence, Set

from flask import g

from constants.roles import SystemRole
from constants.department_roles import DepartmentRole
from models.department import DepartmentMember
from utils.exceptions import BizError

DEPT_ROLE_PRIORITY = {
    DepartmentRole.VIEWER.value: 1,
    DepartmentRole.PROJECT_ADMIN.value: 2,
    DepartmentRole.ADMIN.value: 3,
}


def _normalize_department_role(role: DepartmentRole | str | None) -> Optional[str]:
    if role is None:
        return None
    if isinstance(role, DepartmentRole):
        return role.value
    value = role.strip().lower()
    return value or None


@dataclass
class PermissionScope:
    user_id: int
    system_role: str
    dept_roles: Dict[int, Set[str]] = field(default_factory=dict)
    all_departments: bool = False

    def has_system_role(self, *roles: SystemRole | str) -> bool:
        normalized = {_normalize_system_role_value(r) for r in roles if r}
        if not normalized:
            return False
        return self.system_role in normalized

    def is_system_admin(self) -> bool:
        return self.system_role == SystemRole.ADMIN.value

    def has_department_role(
        self,
        dept_id: int,
        required_role: DepartmentRole | str | None = None,
        include_system_admin: bool = True,
    ) -> bool:
        if dept_id is None:
            return False
        if include_system_admin and self.is_system_admin():
            return True
        roles = self.dept_roles.get(int(dept_id)) or set()
        if not roles:
            return False
        if required_role is None:
            return True
        required_value = _normalize_department_role(required_role)
        if not required_value:
            return True
        required_level = DEPT_ROLE_PRIORITY.get(required_value, 0)
        max_level = max(DEPT_ROLE_PRIORITY.get(role, 0) for role in roles)
        return max_level >= required_level

    def accessible_department_ids(
        self,
        required_role: DepartmentRole | str | None = None,
    ) -> Optional[Sequence[int]]:
        """
        返回允许访问的部门 ID 列表：
          - system admin => None（表示全量）
          - 否则返回白名单
          - required_role 可指定需要的最低部门角色
        """
        if self.all_departments or self.is_system_admin():
            return None
        if required_role is None:
            return list(self.dept_roles.keys())
        required_value = _normalize_department_role(required_role)
        if not required_value:
            return list(self.dept_roles.keys())
        required_level = DEPT_ROLE_PRIORITY.get(required_value, 0)
        allowed = []
        for dept_id, roles in self.dept_roles.items():
            if any(DEPT_ROLE_PRIORITY.get(role, 0) >= required_level for role in roles):
                allowed.append(dept_id)
        return allowed


def _normalize_system_role_value(value: SystemRole | str | None) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, SystemRole):
        return value.value
    return value.strip().lower()


def get_current_user():
    """
    获取当前登录用户（由 auth_required 写入 g.current_user）
    """
    user = getattr(g, "current_user", None)
    if not user:
        raise BizError("未登录", 401)
    return user


def get_permission_scope(default=None) -> PermissionScope | None:
    return getattr(g, "permission_scope", default)


def get_department_scope(user) -> Dict[int, Set[str]]:
    if not user:
        return {}
    memberships = (
        DepartmentMember.query.filter(DepartmentMember.user_id == user.id).all()
    )
    scope: Dict[int, Set[str]] = {}
    for membership in memberships:
        scope.setdefault(membership.department_id, set()).add(membership.role)
    return scope


def build_permission_scope(user) -> PermissionScope:
    if not user:
        raise BizError("未登录", 401)
    dept_scope = get_department_scope(user)
    all_departments = user.role == SystemRole.ADMIN.value
    return PermissionScope(
        user_id=user.id,
        system_role=user.role,
        dept_roles=dept_scope,
        all_departments=all_departments,
    )


def is_system_admin(user=None, scope: PermissionScope | None = None) -> bool:
    scope = scope or get_permission_scope()
    if scope:
        return scope.is_system_admin()
    user = user or getattr(g, "current_user", None)
    if not user:
        return False
    return user.role == SystemRole.ADMIN.value


def is_global_admin(user=None, scope: PermissionScope | None = None) -> bool:
    """
    保持向后兼容的别名
    """
    return is_system_admin(user=user, scope=scope)


def assert_system_admin(user=None, scope: PermissionScope | None = None):
    if not is_system_admin(user=user, scope=scope):
        raise BizError("需要系统管理员权限", 403)


def assert_global_admin(user=None, scope: PermissionScope | None = None):
    assert_system_admin(user=user, scope=scope)


def user_has_department_role(
    dept_id: int,
    required_role: DepartmentRole | str | None = None,
    *,
    user=None,
    scope: PermissionScope | None = None,
    include_system_admin: bool = True,
) -> bool:
    scope = scope or get_permission_scope()
    if scope:
        return scope.has_department_role(
            dept_id,
            required_role=required_role,
            include_system_admin=include_system_admin,
        )
    if user is None:
        user = getattr(g, "current_user", None)
    if not user:
        return False
    if include_system_admin and user.role == SystemRole.ADMIN.value:
        return True
    dept_scope = get_department_scope(user)
    roles = dept_scope.get(int(dept_id))
    if not roles:
        return False
    required_value = _normalize_department_role(required_role)
    if not required_value:
        return True
    required_level = DEPT_ROLE_PRIORITY.get(required_value, 0)
    max_level = max(DEPT_ROLE_PRIORITY.get(role, 0) for role in roles)
    return max_level >= required_level


def assert_dept_admin(dept_id: int, user=None, scope: PermissionScope | None = None):
    if not user_has_department_role(
        dept_id,
        required_role=DepartmentRole.ADMIN,
        user=user,
        scope=scope,
    ):
        raise BizError("无权限（需要部门管理员或系统管理员）", 403)


def user_is_dept_admin(dept_id: int, user=None) -> bool:
    return user_has_department_role(
        dept_id,
        required_role=DepartmentRole.ADMIN,
        user=user,
    )


def user_in_department(
    dept_id: int,
    user=None,
    include_global_admin: bool = True,
    scope: PermissionScope | None = None,
) -> bool:
    return user_has_department_role(
        dept_id,
        user=user,
        scope=scope,
        include_system_admin=include_global_admin,
    )


def assert_user_in_department(
    dept_id: int,
    user=None,
    include_global_admin: bool = True,
    scope: PermissionScope | None = None,
):
    if not user_in_department(
        dept_id,
        user=user,
        include_global_admin=include_global_admin,
        scope=scope,
    ):
        raise BizError("无权限（用户不属于该部门）", 403)
