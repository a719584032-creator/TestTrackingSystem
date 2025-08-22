# -*- coding: utf-8 -*-
"""
tag.py
--------------------------------------------------------------------
通用标签系统：
- Tag: 项目下定义的标签（名称+颜色）。
- TagMap: 多态映射到不同实体（case/plan/run/result/device）。
应用场景：
- 用例分类（冒烟/回归/安全）。
- 计划分组（版本标签）。
- 执行结果标记（需要复测 / 数据缺失）。
性能：
- 针对高并发标签筛选，可考虑添加 (target_type, target_id, tag_id) 复合索引（当前唯一约束已可支撑）。
"""

from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS


class Tag(TimestampMixin, db.Model):
    __tablename__ = "tag"
    __table_args__ = (
        db.UniqueConstraint("project_id", "name", name="uq_tag_project_name"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    color = db.Column(db.String(16))  # #RRGGBB 或 token

    project = db.relationship("Project", backref=db.backref("tags", cascade="all, delete-orphan"))
    mappings = db.relationship("TagMap", back_populates="tag", cascade="all, delete-orphan")


class TagMap(TimestampMixin, db.Model):
    __tablename__ = "tag_map"
    __table_args__ = (
        db.Index("ix_tag_map_target", "target_type", "target_id"),
        db.UniqueConstraint("tag_id", "target_type", "target_id", name="uq_tag_map_tag_target"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey("tag.id", ondelete="CASCADE"), nullable=False)
    target_type = db.Column(db.String(32), nullable=False)  # case / plan / run / result / device
    target_id = db.Column(db.Integer, nullable=False)

    tag = db.relationship("Tag", back_populates="mappings")
