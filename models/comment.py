# -*- coding: utf-8 -*-
"""
comment.py
--------------------------------------------------------------------
通用评论系统：
- 通过 target_type + target_id 支持对计划/用例/快照/执行批次/结果/项目/设备等实体的评论。
- 统一表便于做全文索引、审核、敏感词过滤。
扩展：
- 可加入 parent_id 构建线程式评论。
- 加入 is_edited / edited_at。
审计：
- 结合操作日志（另建 audit_log）可重建评论行为。
"""


from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS

class Comment(TimestampMixin, db.Model):
    __tablename__ = "comment"
    __table_args__ = (
        db.Index("ix_comment_target", "target_type", "target_id"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    author_user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    target_type = db.Column(db.String(32), nullable=False)  # plan / case / plan_case / run / result / project / device
    target_id = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)

    author = db.relationship("User", backref=db.backref("comments", passive_deletes=True))