# -*- coding: utf-8 -*-
"""
attachment.py
--------------------------------------------------------------------
通用附件系统：
- 与 Comment 设计类似，目标实体通过 target_type + target_id。
- stored_file_name 用于存储层实际文件名（避免冲突），file_name 为原始上传名。
安全建议：
- 存储时进行 MIME 校验与扩展名白名单。
- 关键文件下载需鉴权 + 临时 URL。
可扩展：
- hash_sha256, virus_scan_status, encryption_flag。
"""


from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS


class Attachment(TimestampMixin, db.Model):
    __tablename__ = "attachment"
    __table_args__ = (
        db.Index("ix_attachment_target", "target_type", "target_id"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    target_type = db.Column(db.String(32), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    stored_file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    mime_type = db.Column(db.String(128))
    size = db.Column(db.Integer)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))

    uploader = db.relationship("User", backref=db.backref("attachments", passive_deletes=True))

    def to_dict(self):
        return {
            "id": self.id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "file_name": self.file_name,
            "stored_file_name": self.stored_file_name,
            "file_path": self.file_path,
            "mime_type": self.mime_type,
            "size": self.size,
            "uploaded_by": self.uploaded_by,
            "uploaded_at": self.created_at.isoformat() if self.created_at else None,
        }

