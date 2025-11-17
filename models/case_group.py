# -*- coding: utf-8 -*-
"""
case_group.py
--------------------------------------------------------------------
用例分组（目录树）：
- 每个部门独立的用例库，通过 department_id 隔离
- 通过 parent_id 构建多层级目录树
- path 字段存储完整路径（如 root/项目A/模块1/）
- 用户可自由创建目录结构，无业务约束
"""

from extensions.database import db
from .mixins import TimestampMixin, SoftDeleteMixin, COMMON_TABLE_ARGS


class CaseGroup(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "case_group"
    __table_args__ = (
        db.Index("ix_case_group_dept_parent", "department_id", "parent_id"),
        db.Index("ix_case_group_path", "department_id", "path"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("department.id", ondelete="CASCADE"),
        nullable=False
    )
    parent_id = db.Column(
        db.Integer,
        db.ForeignKey("case_group.id", ondelete="CASCADE")
    )
    name = db.Column(db.String(128), nullable=False)
    path = db.Column(db.String(512), nullable=False)  # root/项目A/模块1
    order_no = db.Column(db.Integer, nullable=False, server_default="0")

    # 创建者
    created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    updated_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))

    # 关系
    department = db.relationship("Department", backref=db.backref("case_groups", lazy="dynamic"))
    parent = db.relationship(
        "CaseGroup",
        remote_side=[id],
        backref=db.backref("children", lazy="dynamic")
    )
    test_cases = db.relationship(
        "TestCase",
        back_populates="group",
        lazy="dynamic"
    )
