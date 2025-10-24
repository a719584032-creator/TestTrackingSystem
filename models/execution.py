# -*- coding: utf-8 -*-
"""
execution.py
--------------------------------------------------------------------
执行体系：
1. ExecutionRun: 单次批量执行活动（一次测试会话/迭代），包含统计汇总字段。
   - total/executed/passed 等冗余字段用于快速汇总展示（通过任务或触发更新）。
   - status: running / finished / aborted。
2. ExecutionResult: 针对某条 PlanCase + (设备) 的具体执行结果。
   - run_id + plan_case_id + device_model_id 唯一。
   - result: pending / pass / fail / block / skip。
   - 可扩展：日志路径、自动化脚本输出、指标数据(JSON)。
设计思路：
- 分离“批次”与“结果”以支持多次复测、并行执行。
- 每次新 run 生成对应的 ExecutionResult 初始记录（状态 pending）。
统计更新策略建议：
- 方式 A：应用层每次执行结果更新时增量更新 run 统计列。
- 方式 B：周期性后台任务扫描并重算（避免并发锁）。
"""

from sqlalchemy import and_
from sqlalchemy.orm import foreign

from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS
from .attachment import Attachment
from utils.datetime_helpers import datetime_to_beijing_iso


EXECUTION_RESULT_ATTACHMENT_TYPE = "execution_result"
EXECUTION_RESULT_LOG_ATTACHMENT_TYPE = "execution_result_log"


class ExecutionRun(TimestampMixin, db.Model):
    __tablename__ = "execution_run"
    __table_args__ = (
        db.Index("ix_execution_run_plan_status", "plan_id", "status"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("test_plan.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    run_type = db.Column(db.String(32), nullable=False, server_default="manual")  # manual / scheduled / api
    status = db.Column(db.String(32), nullable=False, server_default="running")  # running / finished / aborted
    triggered_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)

    # 冗余统计列
    total = db.Column(db.Integer, nullable=False, server_default="0")
    executed = db.Column(db.Integer, nullable=False, server_default="0")
    passed = db.Column(db.Integer, nullable=False, server_default="0")
    failed = db.Column(db.Integer, nullable=False, server_default="0")
    blocked = db.Column(db.Integer, nullable=False, server_default="0")
    skipped = db.Column(db.Integer, nullable=False, server_default="0")
    not_run = db.Column(db.Integer, nullable=False, server_default="0")

    test_plan = db.relationship("TestPlan", back_populates="execution_runs")
    trigger_user = db.relationship("User", backref=db.backref("execution_runs", passive_deletes=True))
    execution_results = db.relationship("ExecutionResult", back_populates="execution_run", cascade="all, delete-orphan")

    def to_dict(self, include_results: bool = False):
        data = {
            "id": self.id,
            "plan_id": self.plan_id,
            "name": self.name,
            "run_type": self.run_type,
            "status": self.status,
            "triggered_by": self.triggered_by,
            "start_time": datetime_to_beijing_iso(self.start_time),
            "end_time": datetime_to_beijing_iso(self.end_time),
            "total": self.total,
            "executed": self.executed,
            "passed": self.passed,
            "failed": self.failed,
            "blocked": self.blocked,
            "skipped": self.skipped,
            "not_run": self.not_run,
        }
        if include_results:
            data["execution_results"] = [r.to_dict() for r in self.execution_results]
        return data


class ExecutionResult(TimestampMixin, db.Model):
    __tablename__ = "execution_result"
    __table_args__ = (
        db.UniqueConstraint("run_id", "plan_case_id", "device_model_id", name="uq_execution_result_run_case_device"),
        db.Index("ix_execution_result_run_status", "run_id", "result"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("execution_run.id", ondelete="CASCADE"), nullable=False)
    plan_case_id = db.Column(db.Integer, db.ForeignKey("plan_case.id", ondelete="CASCADE"), nullable=False)
    device_model_id = db.Column(db.Integer, db.ForeignKey("device_model.id", ondelete="SET NULL"))
    plan_device_model_id = db.Column(db.Integer, db.ForeignKey("plan_device_model.id", ondelete="SET NULL"))
    result = db.Column(db.String(32), nullable=False, server_default="pending")  # pending / pass / fail / block / skip
    executed_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    executed_at = db.Column(db.DateTime)
    execution_start_time = db.Column(db.DateTime)
    execution_end_time = db.Column(db.DateTime)
    duration_ms = db.Column(db.Integer)
    failure_reason = db.Column(db.Text)
    bug_ref = db.Column(db.String(128))
    remark = db.Column(db.Text)

    execution_run = db.relationship("ExecutionRun", back_populates="execution_results")
    plan_case = db.relationship("PlanCase", back_populates="execution_results")
    device_model = db.relationship("DeviceModel", back_populates="execution_results")
    plan_device_model = db.relationship("PlanDeviceModel", back_populates="execution_results")
    executor = db.relationship("User", backref=db.backref("execution_results", passive_deletes=True))
    logs = db.relationship(
        "ExecutionResultLog",
        back_populates="execution_result",
        cascade="all, delete-orphan",
        order_by="ExecutionResultLog.executed_at.desc()",
    )
    attachments = db.relationship(
        "Attachment",
        primaryjoin=lambda: and_(
            foreign(Attachment.target_id) == ExecutionResult.id,
            Attachment.target_type == EXECUTION_RESULT_ATTACHMENT_TYPE,
        ),
        viewonly=True,
    )

    def to_dict(
        self,
        *,
        include_attachments: bool = True,
        include_history: bool = True,
    ):
        device_name = None
        device_model_code = None
        device_category = None
        device_payload = None

        if self.plan_device_model:
            device_name = self.plan_device_model.snapshot_name or (
                self.plan_device_model.device_model.name
                if self.plan_device_model.device_model
                else None
            )
            device_model_code = self.plan_device_model.snapshot_model_code or (
                self.plan_device_model.device_model.model_code
                if self.plan_device_model.device_model
                else None
            )
            device_category = self.plan_device_model.snapshot_category or (
                self.plan_device_model.device_model.category
                if self.plan_device_model.device_model
                else None
            )
            device_payload = self.plan_device_model.to_dict()
        elif self.device_model:
            device_name = self.device_model.name
            device_model_code = self.device_model.model_code
            device_category = self.device_model.category
            device_payload = {
                "id": self.device_model_id,
                "name": device_name,
                "model_code": device_model_code,
                "category": device_category,
            }

        executor_name = self.executor.username if self.executor else None
        executor_payload = None
        if self.executor or self.executed_by is not None:
            executor_payload = {
                "id": self.executed_by,
                "username": executor_name,
            }

        data = {
            "id": self.id,
            "run_id": self.run_id,
            "plan_case_id": self.plan_case_id,
            "device_model_id": self.device_model_id,
            "plan_device_model_id": self.plan_device_model_id,
            "result": self.result,
            "executed_by": self.executed_by,
            "executed_by_name": executor_name,
            "executor": executor_payload,
            "executed_at": datetime_to_beijing_iso(self.executed_at),
            "execution_start_time": datetime_to_beijing_iso(self.execution_start_time),
            "execution_end_time": datetime_to_beijing_iso(self.execution_end_time),
            "duration_ms": self.duration_ms,
            "failure_reason": self.failure_reason,
            "bug_ref": self.bug_ref,
            "remark": self.remark,
            "device_model_name": device_name,
            "device_model_code": device_model_code,
            "device_model_category": device_category,
            "device_model": device_payload,
        }

        if include_attachments:
            data["attachments"] = [attachment.to_dict() for attachment in self.attachments]

        if include_history:
            data["history"] = [log.to_dict() for log in self.logs]

        return data


class ExecutionResultLog(TimestampMixin, db.Model):
    __tablename__ = "execution_result_log"
    __table_args__ = (
        db.Index("ix_execution_result_log_result", "execution_result_id", "created_at"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    execution_result_id = db.Column(
        db.Integer,
        db.ForeignKey("execution_result.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id = db.Column(db.Integer, nullable=False)
    plan_case_id = db.Column(db.Integer, nullable=False)
    device_model_id = db.Column(db.Integer)
    result = db.Column(db.String(32), nullable=False)
    executed_by = db.Column(db.Integer)
    executed_at = db.Column(db.DateTime)
    execution_start_time = db.Column(db.DateTime)
    execution_end_time = db.Column(db.DateTime)
    duration_ms = db.Column(db.Integer)
    failure_reason = db.Column(db.Text)
    bug_ref = db.Column(db.String(128))
    remark = db.Column(db.Text)

    execution_result = db.relationship("ExecutionResult", back_populates="logs")
    attachments = db.relationship(
        "Attachment",
        primaryjoin=lambda: and_(
            foreign(Attachment.target_id) == ExecutionResultLog.id,
            Attachment.target_type == EXECUTION_RESULT_LOG_ATTACHMENT_TYPE,
        ),
        viewonly=True,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "execution_result_id": self.execution_result_id,
            "run_id": self.run_id,
            "plan_case_id": self.plan_case_id,
            "device_model_id": self.device_model_id,
            "result": self.result,
            "executed_by": self.executed_by,
            "executed_at": datetime_to_beijing_iso(self.executed_at),
            "execution_start_time": datetime_to_beijing_iso(self.execution_start_time),
            "execution_end_time": datetime_to_beijing_iso(self.execution_end_time),
            "duration_ms": self.duration_ms,
            "failure_reason": self.failure_reason,
            "bug_ref": self.bug_ref,
            "remark": self.remark,
            "attachments": [attachment.to_dict() for attachment in self.attachments],
        }
