from __future__ import annotations

from typing import Iterable, Mapping

from extensions.database import db
from models.attachment import Attachment


class AttachmentRepository:
    """附件相关的持久化操作。

    当前仓储层仅负责写入数据库元数据（文件原始名、存储名、路径等），
    真正的文件上传/下载需要由调用方在写入前完成。例如可以参考
    ``tests/tests_upload_s3.py`` 中使用 ``AWS_BUCKET_NAME=tts-test`` 的示例，
    通过对象存储（S3 兼容接口）将文件上传后，再把生成的 ``stored_file_name``
    和 ``file_path`` 回填到数据库。这样仓储层就只存储指向真实存储位置的
    描述信息，而不会直接操作对象存储。"""

    @staticmethod
    def replace_target_attachments(target_type: str, target_id: int, payloads: Iterable[Mapping]):
        """替换某个实体上的附件列表。"""

        db.session.query(Attachment).filter(
            Attachment.target_type == target_type,
            Attachment.target_id == target_id,
        ).delete(synchronize_session=False)
        for item in payloads:
            AttachmentRepository.add_attachment(target_type, target_id, item)

    @staticmethod
    def add_attachment(target_type: str, target_id: int, payload: Mapping) -> Attachment:
        attachment = Attachment(
            target_type=target_type,
            target_id=target_id,
            file_name=payload.get("file_name"),
            stored_file_name=payload.get("stored_file_name"),
            file_path=payload.get("file_path"),
            mime_type=payload.get("mime_type"),
            size=payload.get("size"),
            uploaded_by=payload.get("uploaded_by"),
        )
        db.session.add(attachment)
        return attachment

