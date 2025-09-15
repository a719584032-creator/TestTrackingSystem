# -*- coding: utf-8 -*-
"""
project.py
--------------------------------------------------------------------
项目实体及成员：
- Project: 部门内的一个产品/子系统/版本域。
- ProjectMember: 用户在项目内的角色（tester / maintainer / owner 等）。
用途：
- 用例、计划、标签、执行统计等均以 Project 作为业务边界。
- 权限控制：优先项目成员，继承部门策略。
"""

from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS


class Project(TimestampMixin, db.Model):
    __tablename__ = "project"
    __table_args__ = (
        db.UniqueConstraint("department_id", "name", name="uq_project_dept_name"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(
        db.Integer, db.ForeignKey("department.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.String(128), nullable=False)
    code = db.Column(db.String(64), unique=True)
    status = db.Column(db.String(32), nullable=False, server_default="active")
    description = db.Column(db.Text)
    owner_user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="SET NULL")
    )

    department = db.relationship("Department", back_populates="projects")
    owner = db.relationship(
        "User", backref=db.backref("owned_projects", passive_deletes=True)
    )
    test_plans = db.relationship(
        "TestPlan", back_populates="project", cascade="all, delete-orphan"
    )
    members = db.relationship(
        "ProjectMember", back_populates="project", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "department_id": self.department_id,
            "name": self.name,
            "code": self.code,
            "status": self.status,
            "description": self.description,
            "owner_user_id": self.owner_user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ProjectMember(TimestampMixin, db.Model):
    __tablename__ = "project_member"
    __table_args__ = (
        db.UniqueConstraint("project_id", "user_id", name="uq_project_member_project_user"),
        COMMON_TABLE_ARGS,
    )
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    role = db.Column(db.String(32), nullable=False, server_default="tester")

    project = db.relationship("Project", back_populates="members")
    user = db.relationship(
        "User", backref=db.backref("project_memberships", cascade="all, delete-orphan")
    )
