# constants/department_roles.py
from enum import Enum


class DepartmentRole(str, Enum):
    ADMIN = "dept_admin"
    PROJECT_ADMIN = "dept_project_admin"
    VIEWER = "dept_member"


DEPARTMENT_ROLE_SET = {r.value for r in DepartmentRole}

# 可选：中文标签
DEPARTMENT_ROLE_LABELS_ZH = {
    DepartmentRole.ADMIN.value: "部门管理员",
    DepartmentRole.PROJECT_ADMIN.value: "项目管理员",
    DepartmentRole.VIEWER.value: "普通成员",
}
