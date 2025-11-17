# -*- coding: utf-8 -*-
"""models/plan_tester.py
--------------------------------------------------------------------
测试计划执行人员关联表：
- 记录哪些用户被授权执行某个测试计划。
- 仅允许这些人员（或具备更高权限的管理员）录入执行结果。
"""

from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS


class TestPlanTester(TimestampMixin, db.Model):
    __tablename__ = "test_plan_tester"
    __table_args__ = (
        db.UniqueConstraint("plan_id", "user_id", name="uq_test_plan_tester_plan_user"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("test_plan.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)

    test_plan = db.relationship("TestPlan", back_populates="plan_testers")
    tester = db.relationship("User", backref=db.backref("plan_assignments", cascade="all, delete-orphan"))

    def to_dict(self):
        username = self.tester.username if self.tester else None
        user = None
        if self.tester:
            user = {
                "id": self.tester.id,
                "username": username,
                "email": self.tester.email,
                "role": self.tester.role,
            }
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "user_id": self.user_id,
            "name": username,
            "tester": user,
        }
