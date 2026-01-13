# -*- coding: utf-8 -*-
"""
feiyan_plan_case_result.py
--------------------------------------------------------------------
飞雁导入用例与执行结果（外部系统数据，仅用于结果回写）。
"""

from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS


class FeiyanPlanCaseResult(TimestampMixin, db.Model):
    __tablename__ = "feiyan_plan_case_result"
    __table_args__ = (
        db.Index("ix_feiyan_case_plan", "plan_id_ext"),
        db.UniqueConstraint("case_id_ext", name="uq_feiyan_case_id_ext"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    plan_id_ext = db.Column(db.String(64), nullable=False, index=True)
    case_id_ext = db.Column(db.String(128), nullable=False, unique=True, index=True)
    case_title = db.Column(db.String(255))
    priority = db.Column(db.String(32))
    group_path = db.Column(db.String(512))
    case_target = db.Column(db.Text)
    preconditions = db.Column(db.Text)
    steps_json = db.Column(db.JSON)
    expected_result = db.Column(db.Text)
    keywords_json = db.Column(db.JSON)
    workload_minutes = db.Column(db.Integer)
    device_id_ext = db.Column(db.String(64))
    device_name = db.Column(db.String(255))
    executed_by_id = db.Column(db.String(64))
    executed_by_name = db.Column(db.String(255))
    execution_start_time = db.Column(db.String(64))
    execution_end_time = db.Column(db.String(64))
    run_result = db.Column(db.String(32))
    remark = db.Column(db.Text)
    failure_reason = db.Column(db.Text)
    bug_ref = db.Column(db.String(128))
    attachments_json = db.Column(db.JSON)

    def to_dict(self):
        return {
            "id": self.id,
            "plan_id": self.plan_id_ext,
            "case_id": self.case_id_ext,
            "title": self.case_title,
            "priority": self.priority,
            "group_path": self.group_path,
            "target": self.case_target,
            "preconditions": self.preconditions,
            "steps": self.steps_json,
            "expected_result": self.expected_result,
            "keywords": self.keywords_json,
            "workload_minutes": self.workload_minutes,
            "device_id": self.device_id_ext,
            "device_name": self.device_name,
            "executed_by_id": self.executed_by_id,
            "executed_by_name": self.executed_by_name,
            "execution_start_time": self.execution_start_time,
            "execution_end_time": self.execution_end_time,
            "run_result": self.run_result,
            "remark": self.remark,
            "failure_reason": self.failure_reason,
            "bug_ref": self.bug_ref,
            "attachments": self.attachments_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
