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

from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS


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
    duration_ms = db.Column(db.Integer)
    failure_reason = db.Column(db.Text)
    bug_ref = db.Column(db.String(128))
    remark = db.Column(db.Text)

    execution_run = db.relationship("ExecutionRun", back_populates="execution_results")
    plan_case = db.relationship("PlanCase", back_populates="execution_results")
    device_model = db.relationship("DeviceModel", back_populates="execution_results")
    plan_device_model = db.relationship("PlanDeviceModel", back_populates="execution_results")
    executor = db.relationship("User", backref=db.backref("execution_results", passive_deletes=True))
