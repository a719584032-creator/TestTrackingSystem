# -*- coding: utf-8 -*-
"""
feiyan_test_plan.py
--------------------------------------------------------------------
飞雁导入测试计划（外部系统数据，仅用于结果回写）。
"""

from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS


class FeiyanTestPlan(TimestampMixin, db.Model):
    __tablename__ = "feiyan_test_plan"
    __table_args__ = (
        db.Index("ix_feiyan_plan_dept", "dept_id_ext"),
        db.Index("ix_feiyan_plan_project", "project_id_ext"),
        COMMON_TABLE_ARGS,
    )

    plan_id_ext = db.Column(db.String(64), primary_key=True)
    dept_id_ext = db.Column(db.String(64), nullable=False)
    dept_name = db.Column(db.String(255))
    project_id_ext = db.Column(db.String(64))
    project_name = db.Column(db.String(255))
    plan_name = db.Column(db.String(255))
    plan_start_time = db.Column(db.String(64))
    plan_end_time = db.Column(db.String(64))
    total = db.Column(db.Integer)
    passed = db.Column(db.Integer)
    failed = db.Column(db.Integer)
    blocked = db.Column(db.Integer)
    not_run = db.Column(db.Integer)
    tester_ids = db.Column(db.JSON)
    tester_names = db.Column(db.Text)
    created_by_user_id = db.Column(db.Integer)

    def to_dict(self):
        return {
            "plan_id": self.plan_id_ext,
            "department_id": self.dept_id_ext,
            "department_name": self.dept_name,
            "project_id": self.project_id_ext,
            "project_name": self.project_name,
            "name": self.plan_name,
            "start_time": self.plan_start_time,
            "end_time": self.plan_end_time,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "blocked": self.blocked,
            "not_run": self.not_run,
            "tester_ids": self.tester_ids,
            "tester_names": self.tester_names,
            "created_by_user_id": self.created_by_user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
