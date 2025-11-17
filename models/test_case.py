# -*- coding: utf-8 -*-
"""
test_case.py
--------------------------------------------------------------------
测试用例实体：
- 属于部门，通过 group_id 关联到目录
- 添加 workload_minutes 字段记录预估工时
- 支持软删除
- 通过 TestCaseHistory 记录所有变更历史
"""

from extensions.database import db
from .mixins import TimestampMixin, SoftDeleteMixin, VersionMixin, COMMON_TABLE_ARGS
from constants.test_case import TestCasePriority, TestCaseStatus, TestCaseType


class TestCase(TimestampMixin, SoftDeleteMixin, VersionMixin, db.Model):
    __tablename__ = "test_case"
    __table_args__ = (
        db.Index("ix_test_case_dept_group", "department_id", "group_id"),
        db.Index("ix_test_case_dept_status", "department_id", "status"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)

    # 部门归属
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("department.id", ondelete="CASCADE"),
        nullable=False
    )

    # 所属目录
    group_id = db.Column(
        db.Integer,
        db.ForeignKey("case_group.id", ondelete="SET NULL")
    )

    # 基本信息
    title = db.Column(db.String(255), nullable=False)
    preconditions = db.Column(db.Text)
    # 例如：[{"no":1,"action":"输入账号","keyword":"输入","note":"...","expected":"..."}]
    steps = db.Column(db.JSON, nullable=False, default=list)
    expected_result = db.Column(db.Text)
    keywords = db.Column(db.JSON, nullable=False, default=list)

    # 优先级、状态、类型
    priority = db.Column(
        db.String(16),
        nullable=False,
        server_default=TestCasePriority.P2.value
    )
    status = db.Column(
        db.String(32),
        nullable=False,
        server_default=TestCaseStatus.ACTIVE.value
    )
    case_type = db.Column(
        db.String(64),
        nullable=False,
        server_default=TestCaseType.FUNCTIONAL.value
    )

    # 工时（分钟）
    workload_minutes = db.Column(db.Integer)

    # # 版本号（每次修改递增）
    # version = db.Column(db.Integer, nullable=False, server_default="1")

    # 创建者和更新者
    created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    updated_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))

    # 关系
    department = db.relationship("Department", back_populates="test_cases")
    group = db.relationship("CaseGroup", back_populates="test_cases")
    creator = db.relationship(
        "User",
        foreign_keys=[created_by],
        backref=db.backref("created_cases", lazy="dynamic")
    )
    updater = db.relationship(
        "User",
        foreign_keys=[updated_by],
        backref=db.backref("updated_cases", lazy="dynamic")
    )

    # 历史记录
    histories = db.relationship(
        "TestCaseHistory",
        back_populates="test_case",
        lazy="dynamic",
        order_by="TestCaseHistory.version.desc()"
    )

    # 计划用例
    plan_cases = db.relationship(
        "PlanCase",
        back_populates="origin_case",
        lazy="dynamic"
    )
