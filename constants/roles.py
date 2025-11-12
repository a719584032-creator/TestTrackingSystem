from __future__ import annotations

from enum import Enum


class SystemRole(str, Enum):
    """
    纯系统层角色：
    - 仅负责用户生命周期、系统配置等全局操作
    - 与部门/项目内角色彻底解耦
    """

    ADMIN = "sys_admin"        # 拥有所有系统级权限
    OPERATOR = "sys_operator"  # 运维 / 系统操作员
    VIEWER = "sys_viewer"      # 系统只读

    @classmethod
    def values(cls) -> list[str]:
        return [role.value for role in cls]

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls.values()


# 兼容历史引用
Role = SystemRole

# 中文展示（可扩展多语言）
ROLE_LABELS_ZH: dict[str, str] = {
    SystemRole.ADMIN.value: "系统管理员",
    SystemRole.OPERATOR.value: "系统操作员",
    SystemRole.VIEWER.value: "系统观察员",
}

# 英文展示名（如果需要）
ROLE_LABELS_EN: dict[str, str] = {
    SystemRole.ADMIN.value: "System Administrator",
    SystemRole.OPERATOR.value: "System Operator",
    SystemRole.VIEWER.value: "System Viewer",
}

# 主动暴露可供快速使用的集合
ALL_ROLES: set[str] = set(SystemRole.values())

DEFAULT_SYSTEM_ROLE = SystemRole.VIEWER


def normalize_role(raw: str | None, default: SystemRole = DEFAULT_SYSTEM_ROLE) -> str:
    """
    清洗外部传入的 system_role 值：
    - None 或空 => 默认
    - 去掉首尾空白
    - 转为小写
    - 校验是否在已注册角色中
    """
    if not raw:
        return default.value
    value = raw.strip().lower()
    if value not in ALL_ROLES:
        raise ValueError(f"非法系统角色: {raw}")
    return value


normalize_system_role = normalize_role
