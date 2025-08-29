# models/mixins.py
from sqlalchemy import func, DateTime
from datetime import datetime
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
    """软删除混入类"""
    is_deleted = db.Column(
        db.Boolean,
        nullable=False,
        server_default="0",
        index=True,
        comment="是否已删除"
    )
    deleted_at = db.Column(
        DateTime,
        comment="删除时间"
    )
    deleted_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="SET NULL"),
        comment="删除人ID"
    )

    @property
    def deleted(self):
        """是否已删除的属性"""
        return self.is_deleted

    def soft_delete(self, user_id=None):
        """
        执行软删除
        :param user_id: 执行删除操作的用户ID
        """
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by = user_id

    def restore(self):
        """恢复软删除的记录"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None

    @classmethod
    def query_active(cls):
        """
        查询未删除的记录
        使用示例: TestCase.query_active().filter_by(department_id=1).all()
        """
        return cls.query.filter_by(is_deleted=False)

    @classmethod
    def query_deleted(cls):
        """
        查询已删除的记录
        使用示例: TestCase.query_deleted().filter_by(department_id=1).all()
        """
        return cls.query.filter_by(is_deleted=True)

    @classmethod
    def query_all(cls):
        """
        查询所有记录（包括已删除的）
        使用示例: TestCase.query_all().filter_by(department_id=1).all()
        """
        return cls.query


class AuditMixin:
    """
    审计混入类 - 记录创建者和更新者
    注意：需要在使用此 Mixin 的模型中定义与 User 的关系
    """
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="SET NULL"),
        comment="创建人ID"
    )
    updated_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="SET NULL"),
        comment="最后更新人ID"
    )

    def set_creator(self, user_id):
        """设置创建者"""
        self.created_by = user_id
        self.updated_by = user_id

    def set_updater(self, user_id):
        """设置更新者"""
        self.updated_by = user_id


class VersionMixin:
    """版本控制混入类"""
    version = db.Column(
        db.Integer,
        nullable=False,
        server_default="1",
        comment="版本号"
    )

    def increment_version(self):
        """递增版本号"""
        self.version = (self.version or 0) + 1

    def get_version(self):
        """获取当前版本号"""
        return self.version or 1


# 组合混入类，方便使用
class BaseModelMixin(TimestampMixin, SoftDeleteMixin):
    """基础模型混入 - 包含时间戳和软删除"""
    pass


class AuditableModelMixin(TimestampMixin, SoftDeleteMixin, AuditMixin):
    """可审计模型混入 - 包含时间戳、软删除和审计"""
    pass


class VersionedModelMixin(TimestampMixin, SoftDeleteMixin, AuditMixin, VersionMixin):
    """版本化模型混入 - 包含所有功能"""
    pass
