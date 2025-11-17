# -*- coding: utf-8 -*-
"""
device_model.py
--------------------------------------------------------------------
被测设备/运行环境模型（DeviceModel）：
- 与 Department 绑定，便于跨项目复用或隔离。
- 可扩展字段：硬件版本、系统版本、配置 JSON。
- 在执行结果 ExecutionResult 中体现维度差异（同一用例在不同设备上的结果）。
性能建议：
- (department_id, active) 索引用于活跃设备过滤列表。
"""

from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS


class DeviceModel(TimestampMixin, db.Model):
    __tablename__ = "device_model"
    __table_args__ = (
        db.Index("ix_device_model_dept_active", "department_id", "active"),
        db.UniqueConstraint("department_id", "name", name="uq_device_model_dept_name"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(
        db.Integer, db.ForeignKey("department.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(64))
    model_code = db.Column(db.String(64))
    vendor = db.Column(db.String(128))
    firmware_version = db.Column(db.String(64))
    description = db.Column(db.Text)
    attributes_json = db.Column(db.JSON)
    active = db.Column(db.Boolean, nullable=False, server_default="1")

    department = db.relationship("Department", back_populates="device_models")
    plan_device_models = db.relationship(
        "PlanDeviceModel", back_populates="device_model", cascade="all, delete-orphan"
    )
    execution_results = db.relationship("ExecutionResult", back_populates="device_model")

    def to_dict(self):
        return {
            "id": self.id,
            "department_id": self.department_id,
            "name": self.name,
            "category": self.category,
            "model_code": self.model_code,
            "vendor": self.vendor,
            "firmware_version": self.firmware_version,
            "description": self.description,
            "attributes_json": self.attributes_json,
            "active": bool(self.active),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
