# -*- coding: utf-8 -*-
"""
department.py
--------------------------------------------------------------------
部门与部门成员关系：
- Department: 组织单元，可用于权限隔离 / 统计 / 成本核算。
- DepartmentMember: 关联 User 与 Department，并赋予部门内角色（dept_admin/dept_viewer 等）。
典型使用：
- 限制用户可见的用例/计划/设备模型。
- 部门维度 KPI 统计（用例数量 / 执行率）。
"""

from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS


class Department(TimestampMixin, db.Model):
    __tablename__ = "department"
    __table_args__ = (COMMON_TABLE_ARGS,)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    code = db.Column(db.String(64), unique=True)
    #status = db.Column(db.String(32), nullable=False, server_default="active")
    active = db.Column(db.Boolean, nullable=False, server_default='1')
    description = db.Column(db.Text)

    members = db.relationship("DepartmentMember", back_populates="department", cascade="all, delete-orphan")
    projects = db.relationship("Project", back_populates="department", cascade="all, delete-orphan")
    test_cases = db.relationship("TestCase", back_populates="department", cascade="all, delete-orphan")
    device_models = db.relationship("DeviceModel", back_populates="department")

    def to_dict(self, counts_data=None):
        """优化的to_dict方法，接受预计算的计数数据"""
        data = {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "active": self.active,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if counts_data and self.id in counts_data:
            data["counts"] = counts_data[self.id]

        return data


class DepartmentMember(TimestampMixin, db.Model):
    __tablename__ = "department_member"
    __table_args__ = (
        db.UniqueConstraint("department_id", "user_id", name="uq_department_member_department_user"),
        COMMON_TABLE_ARGS,
    )
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    role = db.Column(db.String(32), nullable=False, server_default="dept_viewer")

    department = db.relationship("Department", back_populates="members")
    user = db.relationship("User", backref=db.backref("department_memberships", cascade="all, delete-orphan"))

    def to_dict(self, user_basic: bool = False):
        data = {
            "id": self.id,
            "department_id": self.department_id,
            "user_id": self.user_id,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if user_basic and self.user:
            data["user"] = {
                "id": self.user.id,
                "username": self.user.username,
                "email": self.user.email,
                "role": self.user.role,
                "active": self.user.active,
            }
        return data
