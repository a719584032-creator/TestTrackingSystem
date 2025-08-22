# -*- coding: utf-8 -*-
"""
test_plan.py
--------------------------------------------------------------------
测试计划：
- 聚合选定的用例（PlanCase 快照） + 目标设备 (PlanDeviceModel)。
- execution_runs 表示该计划的多次执行批次。
- status：draft -> active -> closed。
扩展：
- 可添加字段：risk_level, approval_state, baseline_tag。
"""

from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS


class TestPlan(TimestampMixin, db.Model):
    __tablename__ = "test_plan"
    __table_args__ = (
        db.Index("ix_test_plan_project_status", "project_id", "status"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(32), nullable=False, server_default="draft")  # draft / active / closed
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)

    project = db.relationship("Project", back_populates="test_plans")
    creator = db.relationship("User", backref=db.backref("created_plans", passive_deletes=True))
    plan_cases = db.relationship("PlanCase", back_populates="test_plan", cascade="all, delete-orphan")
    plan_device_models = db.relationship("PlanDeviceModel", back_populates="test_plan", cascade="all, delete-orphan")
    execution_runs = db.relationship("ExecutionRun", back_populates="test_plan", cascade="all, delete-orphan")
