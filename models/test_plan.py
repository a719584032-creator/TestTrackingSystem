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
from constants.test_plan import TestPlanStatus, DEFAULT_PLAN_STATUS


class TestPlan(TimestampMixin, db.Model):
    __tablename__ = "test_plan"
    __table_args__ = (
        db.Index("ix_test_plan_project_status", "project_id", "status"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(32), nullable=False, server_default=DEFAULT_PLAN_STATUS)  # 对齐枚举
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)

    project = db.relationship("Project", back_populates="test_plans")
    creator = db.relationship("User", backref=db.backref("created_plans", passive_deletes=True))
    plan_cases = db.relationship("PlanCase", back_populates="test_plan", cascade="all, delete-orphan")
    plan_device_models = db.relationship("PlanDeviceModel", back_populates="test_plan", cascade="all, delete-orphan")
    execution_runs = db.relationship("ExecutionRun", back_populates="test_plan", cascade="all, delete-orphan")
    plan_testers = db.relationship("TestPlanTester", back_populates="test_plan", cascade="all, delete-orphan")

    def to_dict(
        self,
        include_cases: bool = True,
        include_device_models: bool = True,
        include_testers: bool = True,
        include_runs: bool = True,
    ):
        data = {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project.name if self.project else None,
            "name": self.name,
            "status": self.status,
            "description": self.description,
            "created_by": self.created_by,
            "created_by_name": self.creator.username if self.creator else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_device_models:
            data["device_models"] = [dm.to_dict() for dm in self.plan_device_models]
        if include_testers:
            data["testers"] = [tester.to_dict() for tester in self.plan_testers]
        if include_cases:
            data["cases"] = [case.to_dict() for case in self.plan_cases]
        if include_runs:
            data["execution_runs"] = [run.to_dict() for run in self.execution_runs]

        statistics = {
            "total_results": 0,
            "executed_results": 0,
            "passed": 0,
            "failed": 0,
            "blocked": 0,
            "skipped": 0,
        }
        if self.execution_runs:
            # 默认取最新 run 的统计
            latest_run = max(self.execution_runs, key=lambda r: r.created_at or 0)
            statistics.update(
                total_results=latest_run.total,
                executed_results=latest_run.executed,
                passed=latest_run.passed,
                failed=latest_run.failed,
                blocked=latest_run.blocked,
                skipped=latest_run.skipped,
                not_run=latest_run.not_run,
            )
        data["statistics"] = statistics
        return data

    @property
    def is_archived(self) -> bool:
        return self.status == TestPlanStatus.ARCHIVED.value
