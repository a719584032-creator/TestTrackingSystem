# -*- coding: utf-8 -*-
"""
plan_case.py
--------------------------------------------------------------------
计划用例快照（PlanCase）：
- 记录当时 TestCase 的标题、步骤、预期等。原始用例更新后不影响已生成快照。
- include: 控制是否纳入本次计划统计（可用于临时排除）。
- order_no: 用于在执行 UI 中的排序。
- group_path_cache: 冗余存储当时用例的分组路径，方便统计/过滤。
关键关系：
- 与 ExecutionResult 形成一对多（不同设备或多次执行记录）。
"""

from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS

from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS


class PlanCase(TimestampMixin, db.Model):
    __tablename__ = "plan_case"
    __table_args__ = (
        db.UniqueConstraint("plan_id", "case_id", name="uq_plan_case_plan_case"),
        db.Index("ix_plan_case_plan_priority", "plan_id", "snapshot_priority"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(
        db.Integer,
        db.ForeignKey("test_plan.id", ondelete="CASCADE"),
        nullable=False
    )
    case_id = db.Column(
        db.Integer,
        db.ForeignKey("test_case.id", ondelete="SET NULL")
    )

    # 快照数据
    snapshot_title = db.Column(db.String(255), nullable=False)
    snapshot_steps = db.Column(db.JSON, nullable=False)
    snapshot_expected_result = db.Column(db.Text)
    snapshot_preconditions = db.Column(db.Text)
    snapshot_priority = db.Column(db.String(16), nullable=False)
    snapshot_workload_minutes = db.Column(db.Integer)  # 新增工时快照

    # 控制字段
    include = db.Column(db.Boolean, nullable=False, server_default="1")
    order_no = db.Column(db.Integer, nullable=False, server_default="0")
    group_path_cache = db.Column(db.String(512))  # 缓存用例所在目录路径

    # 关系
    test_plan = db.relationship("TestPlan", back_populates="plan_cases")
    origin_case = db.relationship("TestCase", back_populates="plan_cases")
    execution_results = db.relationship("ExecutionResult", back_populates="plan_case")
