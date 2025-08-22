# -*- coding: utf-8 -*-
"""
test_case.py
--------------------------------------------------------------------
原始用例实体：
- 与 Project + Department 关联（便于跨部门数据审计）。
- 通过 group_id 关联 CaseGroup（可为空：脱离分组）。
- priority/status/case_type 提供基本分类。
- plan_case 为其在某个计划中的“快照”集合。
注意：
- 修改 TestCase 不自动更新已存在 PlanCase（快照设计）。
扩展：
- 可加字段：automation_status, script_path, last_exec_result_id。
"""


from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS

class TestCase(TimestampMixin, db.Model):
    __tablename__ = "test_case"
    __table_args__ = (
        db.Index("ix_test_case_project_status", "project_id", "status"),
        db.Index("ix_test_case_group", "group_id"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id", ondelete="CASCADE"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("case_group.id", ondelete="SET NULL"))
    title = db.Column(db.String(255), nullable=False)
    preconditions = db.Column(db.Text)
    steps = db.Column(db.Text)
    expected_result = db.Column(db.Text)
    priority = db.Column(db.String(16), nullable=False, server_default="P2")  # P0/P1/P2/P3
    status = db.Column(db.String(32), nullable=False, server_default="active")  # active / deprecated
    case_type = db.Column(db.String(64), nullable=False, server_default="functional")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    updated_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))

    group = db.relationship("CaseGroup", back_populates="test_cases")
    department = db.relationship("Department", back_populates="test_cases")
    project = db.relationship("Project", backref=db.backref("test_cases", cascade="all, delete-orphan"))
    creator = db.relationship("User", foreign_keys=[created_by], backref=db.backref("created_cases", passive_deletes=True))
    updater = db.relationship("User", foreign_keys=[updated_by], backref=db.backref("updated_cases", passive_deletes=True))
    plan_cases = db.relationship("PlanCase", back_populates="origin_case")