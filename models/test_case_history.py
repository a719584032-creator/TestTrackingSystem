# -*- coding: utf-8 -*-
"""
test_case_history.py
--------------------------------------------------------------------
用例历史记录：
- 记录每次修改的完整快照
- 包含修改人、修改时间、修改说明
- 可用于版本对比和回滚
"""

from extensions.database import db
from .mixins import COMMON_TABLE_ARGS
from datetime import datetime


class TestCaseHistory(db.Model):
    __tablename__ = "test_case_history"
    __table_args__ = (
        db.Index("ix_test_case_history_case_version", "test_case_id", "version"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    test_case_id = db.Column(
        db.Integer,
        db.ForeignKey("test_case.id", ondelete="CASCADE"),
        nullable=False
    )

    # 版本号
    version = db.Column(db.Integer, nullable=False)

    # 快照数据
    title = db.Column(db.String(255), nullable=False)
    preconditions = db.Column(db.Text)
    steps = db.Column(db.JSON, nullable=False)
    expected_result = db.Column(db.Text)
    keywords = db.Column(db.JSON, nullable=False)
    priority = db.Column(db.String(16), nullable=False)
    status = db.Column(db.String(32), nullable=False)
    case_type = db.Column(db.String(64), nullable=False)
    workload_minutes = db.Column(db.Integer)

    # 变更信息
    change_type = db.Column(db.String(32), nullable=False)  # CREATE, UPDATE, DELETE
    change_summary = db.Column(db.Text)  # 变更说明
    changed_fields = db.Column(db.JSON)  # 记录哪些字段被修改

    # 操作人和时间
    operated_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    operated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # 关系
    test_case = db.relationship("TestCase", back_populates="histories")
    operator = db.relationship("User")
