# models/mixins.py
from sqlalchemy import func, DateTime
from extensions.database import db

COMMON_TABLE_ARGS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}

class TimestampMixin:
    created_at = db.Column(DateTime, nullable=False, server_default=func.now(), index=True)
    updated_at = db.Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), index=True)

class SoftDeleteMixin:
    is_deleted = db.Column(db.Boolean, nullable=False, server_default="0", index=True)