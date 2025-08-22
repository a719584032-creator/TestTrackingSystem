# -*- coding: utf-8 -*-
"""
user.py
--------------------------------------------------------------------
用户实体。
说明：
- 与部门(DepartmentMember) / 项目(ProjectMember) 通过中间表建立多对多与角色。
- role 字段为全局角色：user / admin / auditor 等。
- active 控制账号启用状态，避免直接删除账号导致历史数据失参。
可扩展：
- last_login_at, password_salt, 强制密码轮换策略字段等。
"""

from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS
from constants.roles import Role
from datetime import datetime


class User(TimestampMixin, db.Model):
    __tablename__ = "user"
    __table_args__ = (COMMON_TABLE_ARGS,)

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(20), unique=True)
    role = db.Column(db.String(32), nullable=False, server_default=Role.USER.value)
    active = db.Column(db.Boolean, nullable=False, server_default="1")
    password_version = db.Column(db.Integer, nullable=False, server_default="1")
    password_updated_at = db.Column(db.DateTime)

    def __repr__(self):
        return f"<User id={self.id} username={self.username} role={self.role}>"

    @property
    def role_label(self) -> str:
        from constants.roles import ROLE_LABELS_ZH
        return ROLE_LABELS_ZH.get(self.role, self.role)

    def touch_password_time(self):
        self.password_updated_at = datetime.utcnow()
