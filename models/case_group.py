# -*- coding: utf-8 -*-
"""
case_group.py
--------------------------------------------------------------------
用例分组（层级）：
- 通过 parent_id 构建树；path 字段存储完整路径（如 root/登录/异常/）。
- order_no 控制同级排序。
- 用于管理大量用例结构、批量操作或权限（后续可扩展 group 级权限）。
查询建议：
- 前端展开时，可根据 path 前缀过滤（LIKE 'root/登录/%'）。
- 也可进一步维护 materialized path 索引或冗余 depth 字段。
"""


from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS

class CaseGroup(TimestampMixin, db.Model):
    __tablename__ = "case_group"
    __table_args__ = (
        db.Index("ix_case_group_project_parent", "project_id", "parent_id"),
        db.Index("ix_case_group_path", "project_id", "path"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("case_group.id", ondelete="CASCADE"))
    name = db.Column(db.String(128), nullable=False)
    path = db.Column(db.String(512), nullable=False)  # root/功能A/子模块B
    order_no = db.Column(db.Integer, nullable=False, server_default="0")

    parent = db.relationship("CaseGroup", remote_side=[id],
                             backref=db.backref("children", cascade="all, delete-orphan"))
    test_cases = db.relationship("TestCase", back_populates="group")
    project = db.relationship("Project", backref=db.backref("case_groups", cascade="all, delete-orphan"))