# -*- coding: utf-8 -*-
"""
plan_device_model.py
--------------------------------------------------------------------
计划与设备模型关联：
- 表示该计划需要在某些设备/平台上验证。
- ExecutionResult 可引用 plan_device_model_id 以便统计某计划内每设备执行进度。
"""

from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS


class PlanDeviceModel(TimestampMixin, db.Model):
    __tablename__ = "plan_device_model"
    __table_args__ = (
        db.UniqueConstraint("plan_id", "device_model_id", name="uq_plan_device_model_plan_device"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("test_plan.id", ondelete="CASCADE"), nullable=False)
    device_model_id = db.Column(
        db.Integer,
        db.ForeignKey("device_model.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_name = db.Column(db.String(255), nullable=False)
    snapshot_model_code = db.Column(db.String(255))
    snapshot_category = db.Column(db.String(64))

    test_plan = db.relationship("TestPlan", back_populates="plan_device_models")
    device_model = db.relationship("DeviceModel", back_populates="plan_device_models")
    execution_results = db.relationship("ExecutionResult", back_populates="plan_device_model")

    def to_dict(self):
        name = self.snapshot_name or (self.device_model.name if self.device_model else None)
        model_code = self.snapshot_model_code or (
            self.device_model.model_code if self.device_model else None
        )
        category = self.snapshot_category or (
            self.device_model.category if self.device_model else None
        )
        snapshot = {
            "id": self.device_model_id,
            "name": name,
            "model_code": model_code,
            "category": category,
        }
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "device_model_id": self.device_model_id,
            "name": name,
            "model_code": model_code,
            "category": category,
            "device_model": snapshot,
        }
