from __future__ import annotations
from enum import Enum
from typing import Iterable


class Role(str, Enum):
    """
    系统内角色的机器值枚举：
    - 枚举成员值用于数据库持久化、权限判断
    - 枚举名本身（ADMIN 等）用于代码引用
    """
    ADMIN = "admin"  # 超级管理员 / 平台管理员
    DEPT_ADMIN = "dept_admin"  # 部门管理员
    PROJECT_ADMIN = "project_admin"  # 项目管理员
    USER = "user"  # 普通用户

    @classmethod
    def values(cls) -> list[str]:
        return [r.value for r in cls]

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls.values()


# 中文展示（可扩展多语言）
ROLE_LABELS_ZH: dict[str, str] = {
    Role.ADMIN.value: "系统管理员",
    Role.DEPT_ADMIN.value: "部门管理员",
    Role.PROJECT_ADMIN.value: "项目管理员",
    Role.USER.value: "普通用户",
}

# 英文展示名（如果需要）
ROLE_LABELS_EN: dict[str, str] = {
    Role.ADMIN.value: "Administrator",
    Role.DEPT_ADMIN.value: "Department Admin",
    Role.PROJECT_ADMIN.value: "Project Admin",
    Role.USER.value: "User",
}

# 主动暴露可供快速使用的集合
ALL_ROLES: set[str] = set(Role.values())


# 如果未来有“只读角色”“可创建项目角色”之类的权限分类，可在这里添加派生集合
# 例：
# ROLES_CAN_CREATE_PROJECT = {Role.ADMIN.value, Role.DEPT_ADMIN.value, Role.PROJECT_ADMIN.value}

def normalize_role(raw: str | None, default: Role = Role.USER) -> str:
    """
    清洗外部传入的 role 值：
    - None 或空 => 默认
    - 去掉首尾空白
    - 转为小写
    - 校验是否在已注册角色中
    """
    if not raw:
        return default.value
    value = raw.strip().lower()
    if value not in ALL_ROLES:
        raise ValueError(f"非法角色: {raw}")
    return value
