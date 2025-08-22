# 最终版测试管理系统数据模型（MySQL）

目录建议：
```
├── app.py                    # Flask 应用入口
├── config/                   # 配置相关
│   ├── __init__.py
│   ├── settings.py           # 基础配置类（开发、测试、生产环境、AWS、redis）
├── constants/                # 项目常量
│   ├── __init__.py
│   ├── roles.py
│   ├── department_reles.py
├── extensions/               # 第三方扩展初始化（db, jwt, cache 等）
│   ├── __init__.py
│   ├── database.py           # SQLAlchemy 初始化
│   ├── jwt.py                # JWT 初始化
│   ├── logger.py             # 日志初始化
├── models/                   # ORM 模型
│   ├── __init__.py
│   ├── mixins.py
│   ├── user.py
│   ├── department.py
│   ├── project.py
│   ├── device_model.py
│   ├── test_plan.py
│   ├── plan_case.py
│   ├── plan_device_model.py
│   ├── case_group.py
│   ├── test_case.py
│   ├── execution.py
│   ├── comment.py
│   ├── attachment.py
│   ├── tag.py
├── schemas/                  # 数据序列化与验证
│   ├── __init__.py
├── repositories/             # 数据访问层（DAO）
│   ├── __init__.py
├── services/                 # 业务逻辑层
│   ├── __init__.py
├── controllers/              # 控制器（蓝图路由）
│   ├── __init__.py
├── utils/                    # 工具模块
│   ├── __init__.py
│   ├── response.py           # 统一 API 响应格式
│   ├── exceptions.py         # 自定义异常
│   ├── password.py           # 密码加密/校验
│   ├── datetime_util.py
├── migrations/               # 数据库迁移文件（Flask-Migrate）
├── tests/                    # 单元测试
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_testplan.py
├── requirements.txt          # Python 依赖
├── .env                      # 环境变量（数据库、JWT 密钥等）
├── README.md
```

## 1. extensions/database.py

```python
# extensions/database.py
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData

naming_convention = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

db = SQLAlchemy(metadata=MetaData(naming_convention=naming_convention))
```

## 2. models/mixins.py

```python
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
```

## 3. 用户与组织

### models/user.py
```python
from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS

class User(TimestampMixin, db.Model):
    __tablename__ = "user"
    __table_args__ = (COMMON_TABLE_ARGS,)

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True)
    role = db.Column(db.String(32), nullable=False, server_default="user")  # user / admin / ...
    active = db.Column(db.Boolean, nullable=False, server_default="1")

    def __repr__(self):
        return f"<User id={self.id} username={self.username}>"
```

### models/department.py
```python
from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS

class Department(TimestampMixin, db.Model):
    __tablename__ = "department"
    __table_args__ = (COMMON_TABLE_ARGS,)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    code = db.Column(db.String(64), unique=True)
    status = db.Column(db.String(32), nullable=False, server_default="active")
    description = db.Column(db.Text)

    members = db.relationship("DepartmentMember", back_populates="department", cascade="all, delete-orphan")
    projects = db.relationship("Project", back_populates="department", cascade="all, delete-orphan")
    test_cases = db.relationship("TestCase", back_populates="department")
    device_models = db.relationship("DeviceModel", back_populates="department")

class DepartmentMember(TimestampMixin, db.Model):
    __tablename__ = "department_member"
    __table_args__ = (
        db.UniqueConstraint("department_id", "user_id", name="uq_department_member_department_user"),
        COMMON_TABLE_ARGS,
    )
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    role = db.Column(db.String(32), nullable=False, server_default="dept_viewer")

    department = db.relationship("Department", back_populates="members")
    user = db.relationship("User", backref=db.backref("department_memberships", cascade="all, delete-orphan"))
```

### models/project.py
```python
from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS

class Project(TimestampMixin, db.Model):
    __tablename__ = "project"
    __table_args__ = (
        db.UniqueConstraint("department_id", "name", name="uq_project_dept_name"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    code = db.Column(db.String(64), unique=True)
    status = db.Column(db.String(32), nullable=False, server_default="active")
    description = db.Column(db.Text)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))

    department = db.relationship("Department", back_populates="projects")
    owner = db.relationship("User", backref=db.backref("owned_projects", passive_deletes=True))
    test_plans = db.relationship("TestPlan", back_populates="project", cascade="all, delete-orphan")
    members = db.relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")

class ProjectMember(TimestampMixin, db.Model):
    __tablename__ = "project_member"
    __table_args__ = (
        db.UniqueConstraint("project_id", "user_id", name="uq_project_member_project_user"),
        COMMON_TABLE_ARGS,
    )
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    role = db.Column(db.String(32), nullable=False, server_default="tester")

    project = db.relationship("Project", back_populates="members")
    user = db.relationship("User", backref=db.backref("project_memberships", cascade="all, delete-orphan"))
```

## 4. 设备 / 用例层次 / 用例

### models/device_model.py
```python
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
    department_id = db.Column(db.Integer, db.ForeignKey("department.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    model_code = db.Column(db.String(64))
    vendor = db.Column(db.String(128))
    firmware_version = db.Column(db.String(64))
    attributes_json = db.Column(db.JSON)
    active = db.Column(db.Boolean, nullable=False, server_default="1")

    department = db.relationship("Department", back_populates="device_models")
    plan_device_models = db.relationship("PlanDeviceModel", back_populates="device_model", cascade="all, delete-orphan")
    execution_results = db.relationship("ExecutionResult", back_populates="device_model")
```

### models/case_group.py
```python
from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS

class CaseGroup(TimestampMixin, db.Model):
    __tablename__ = "case_group"
    __table_args__ = (
        db.Index("ix_case_group_project_parent", "project_id", "parent_id"),
        db.Index("ix_case_group_path", "project_id", "path"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("case_group.id", ondelete="CASCADE"))
    name = db.Column(db.String(128), nullable=False)
    path = db.Column(db.String(512), nullable=False)  # root/功能A/子模块B
    order_no = db.Column(db.Integer, nullable=False, server_default="0")

    parent = db.relationship("CaseGroup", remote_side=[id],
                             backref=db.backref("children", cascade="all, delete-orphan"))
    test_cases = db.relationship("TestCase", back_populates="group")
    project = db.relationship("Project", backref=db.backref("case_groups", cascade="all, delete-orphan"))
```

### models/test_case.py
```python
from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS

class TestCase(TimestampMixin, db.Model):
    __tablename__ = "test_case"
    __table_args__ = (
        db.Index("ix_test_case_project_status", "project_id", "status"),
        db.Index("ix_test_case_group", "group_id"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id", ondelete="CASCADE"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("case_group.id", ondelete="SET NULL"))
    title = db.Column(db.String(255), nullable=False)
    preconditions = db.Column(db.Text)
    steps = db.Column(db.Text)
    expected_result = db.Column(db.Text)
    priority = db.Column(db.String(16), nullable=False, server_default="P2")  # P0/P1/P2/P3
    status = db.Column(db.String(32), nullable=False, server_default="active")  # active / deprecated
    case_type = db.Column(db.String(64), nullable=False, server_default="functional")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    updated_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))

    group = db.relationship("CaseGroup", back_populates="test_cases")
    department = db.relationship("Department", backref=db.backref("test_cases", cascade="all, delete-orphan"))
    project = db.relationship("Project", backref=db.backref("test_cases", cascade="all, delete-orphan"))
    creator = db.relationship("User", foreign_keys=[created_by], backref=db.backref("created_cases", passive_deletes=True))
    updater = db.relationship("User", foreign_keys=[updated_by], backref=db.backref("updated_cases", passive_deletes=True))
    plan_cases = db.relationship("PlanCase", back_populates="origin_case")
```

## 5. 计划与快照

### models/test_plan.py
```python
from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS

class TestPlan(TimestampMixin, db.Model):
    __tablename__ = "test_plan"
    __table_args__ = (
        db.Index("ix_test_plan_project_status", "project_id", "status"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(32), nullable=False, server_default="draft")  # draft / active / closed
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)

    project = db.relationship("Project", back_populates="test_plans")
    creator = db.relationship("User", backref=db.backref("created_plans", passive_deletes=True))
    plan_cases = db.relationship("PlanCase", back_populates="test_plan", cascade="all, delete-orphan")
    plan_device_models = db.relationship("PlanDeviceModel", back_populates="test_plan", cascade="all, delete-orphan")
    execution_runs = db.relationship("ExecutionRun", back_populates="test_plan", cascade="all, delete-orphan")
```

### models/plan_case.py
```python
from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS

class PlanCase(TimestampMixin, db.Model):
    __tablename__ = "plan_case"
    __table_args__ = (
        db.UniqueConstraint("plan_id", "case_id", name="uq_plan_case_plan_case"),
        db.Index("ix_plan_case_plan_priority", "plan_id", "snapshot_priority"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("test_plan.id", ondelete="CASCADE"), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey("test_case.id", ondelete="SET NULL"))
    snapshot_title = db.Column(db.String(255), nullable=False)
    snapshot_steps = db.Column(db.Text)
    snapshot_expected_result = db.Column(db.Text)
    snapshot_preconditions = db.Column(db.Text)
    snapshot_priority = db.Column(db.String(16), nullable=False, server_default="P2")
    include = db.Column(db.Boolean, nullable=False, server_default="1")
    order_no = db.Column(db.Integer, nullable=False, server_default="0")
    group_path_cache = db.Column(db.String(512))

    test_plan = db.relationship("TestPlan", back_populates="plan_cases")
    origin_case = db.relationship("TestCase", back_populates="plan_cases")
    execution_results = db.relationship("ExecutionResult", back_populates="plan_case")
```

### models/plan_device_model.py
```python
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
    device_model_id = db.Column(db.Integer, db.ForeignKey("device_model.id", ondelete="CASCADE"), nullable=False)

    test_plan = db.relationship("TestPlan", back_populates="plan_device_models")
    device_model = db.relationship("DeviceModel", back_populates="plan_device_models")
    execution_results = db.relationship("ExecutionResult", back_populates="plan_device_model")
```

## 6. 执行批次 / 结果

### models/execution.py
```python
from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS

class ExecutionRun(TimestampMixin, db.Model):
    __tablename__ = "execution_run"
    __table_args__ = (
        db.Index("ix_execution_run_plan_status", "plan_id", "status"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("test_plan.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    run_type = db.Column(db.String(32), nullable=False, server_default="manual")  # manual / scheduled / api
    status = db.Column(db.String(32), nullable=False, server_default="running")  # running / finished / aborted
    triggered_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)

    # 冗余统计列
    total = db.Column(db.Integer, nullable=False, server_default="0")
    executed = db.Column(db.Integer, nullable=False, server_default="0")
    passed = db.Column(db.Integer, nullable=False, server_default="0")
    failed = db.Column(db.Integer, nullable=False, server_default="0")
    blocked = db.Column(db.Integer, nullable=False, server_default="0")
    skipped = db.Column(db.Integer, nullable=False, server_default="0")
    not_run = db.Column(db.Integer, nullable=False, server_default="0")

    test_plan = db.relationship("TestPlan", back_populates="execution_runs")
    trigger_user = db.relationship("User", backref=db.backref("execution_runs", passive_deletes=True))
    execution_results = db.relationship("ExecutionResult", back_populates="execution_run", cascade="all, delete-orphan")

class ExecutionResult(TimestampMixin, db.Model):
    __tablename__ = "execution_result"
    __table_args__ = (
        db.UniqueConstraint("run_id", "plan_case_id", "device_model_id", name="uq_execution_result_run_case_device"),
        db.Index("ix_execution_result_run_status", "run_id", "result"),
        COMMON_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("execution_run.id", ondelete="CASCADE"), nullable=False)
    plan_case_id = db.Column(db.Integer, db.ForeignKey("plan_case.id", ondelete="CASCADE"), nullable=False)
    device_model_id = db.Column(db.Integer, db.ForeignKey("device_model.id", ondelete="SET NULL"))
    plan_device_model_id = db.Column(db.Integer, db.ForeignKey("plan_device_model.id", ondelete="SET NULL"))
    result = db.Column(db.String(32), nullable=False, server_default="pending")  # pending / pass / fail / block / skip
    executed_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    executed_at = db.Column(db.DateTime)
    duration_ms = db.Column(db.Integer)
    failure_reason = db.Column(db.Text)
    bug_ref = db.Column(db.String(128))
    remark = db.Column(db.Text)

    execution_run = db.relationship("ExecutionRun", back_populates="execution_results")
    plan_case = db.relationship("PlanCase", back_populates="execution_results")
    device_model = db.relationship("DeviceModel", back_populates="execution_results")
    plan_device_model = db.relationship("PlanDeviceModel", back_populates="execution_results")
    executor = db.relationship("User", backref=db.backref("execution_results", passive_deletes=True))
```

## 7. 评论与附件（多态）

### models/comment.py
```python
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
```

### models/attachment.py
```python
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
```

## 8. 标签（可选）

### models/tag.py
```python
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
```

## 9. 汇总导入（确保迁移检出）

### models/__init__.py
```python
from .mixins import TimestampMixin
from .user import User
from .department import Department, DepartmentMember
from .project import Project, ProjectMember
from .device_model import DeviceModel
from .case_group import CaseGroup
from .test_case import TestCase
from .test_plan import TestPlan
from .plan_case import PlanCase
from .plan_device_model import PlanDeviceModel
from .execution import ExecutionRun, ExecutionResult
from .comment import Comment
from .attachment import Attachment
from .tag import Tag, TagMap

__all__ = [
    "TimestampMixin",
    "User", "Department", "DepartmentMember", "Project", "ProjectMember",
    "DeviceModel", "CaseGroup", "TestCase", "TestPlan", "PlanCase",
    "PlanDeviceModel", "ExecutionRun", "ExecutionResult",
    "Comment", "Attachment", "Tag", "TagMap"
]
```

## 10. app.py 初始化示例

```python
from flask import Flask
from flask_migrate import Migrate
from extensions.database import db
from models import *  # noqa

class Config:
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:pass@localhost:3306/testcase_mgt?charset=utf8mb4"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    Migrate(app, db)
    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
```

## 11. 初始迁移（空库直接一次性生成）

执行：
```bash
flask db init         # 仅首次
flask db migrate -m "init full schema v1"
flask db upgrade
```

Alembic 自动生成会列出所有 create_table。  
可根据需要手工添加 engine / charset（通常 Alembic 生成时会自动携带）及索引顺序。

如果你想跳过 Alembic 直接创建（开发快速验证）可执行：
```python
from app import create_app
from extensions.database import db
app = create_app()
with app.app_context():
    db.drop_all()
    db.create_all()
```

但生产仍建议使用 Alembic 管理版本。

## 12. 常见查询索引建议（可按需再补）

| 场景 | 建议索引 |
|------|---------|
| 计划执行结果统计 | execution_result (run_id, result) 已有 |
| 按计划过滤设备 | plan_device_model(plan_id, device_model_id) 唯一约束可用 |
| 用例层次检索 | case_group(project_id, path) 已有 |
| 用例筛选 | test_case(project_id, status), test_case(group_id) |
| 评论拉取 | comment(target_type, target_id) |
| 标签过滤 | tag_map(target_type, target_id) + tag_id（如需反查 tag → objects 已有） |

## 13. 一些可选改进

- 使用 Enum：MySQL 原生 Enum 修改不便，推荐 varchar + CheckConstraint（MySQL 8.0+ 生效）或应用层校验。
- 大表分区：execution_result 可按 run_id HASH 或 executed_at RANGE（后期量大再考虑）。
- 软删除：对 TestCase / TestPlan 引入 SoftDeleteMixin 替代物理删除。

## 14. 简单种子数据脚本（可选）

```python
# scripts/seed.py
from app import create_app
from extensions.database import db
from models import User, Department, DepartmentMember, Project

app = create_app()

with app.app_context():
    db.create_all()
    u = User(username="admin", password_hash="...", role="admin")
    d = Department(name="QA Team", code="QA")
    db.session.add_all([u, d])
    db.session.flush()
    dm = DepartmentMember(department_id=d.id, user_id=u.id, role="dept_admin")
    p = Project(department_id=d.id, name="CorePlatform", code="CORE")
    db.session.add_all([dm, p])
    db.session.commit()
    print("Seed done")
```

## 15. 前后端字段映射提示

| 概念 | 关键主表 | 说明 |
|------|----------|------|
| 用例原始数据 | test_case | 编辑时更新；PlanCase 不随之自动变更（快照） |
| 计划快照 | plan_case | 创建计划或刷新选择时生成 |
| 执行批次 | execution_run | 每次测试执行 session |
| 执行结果 | execution_result | run 内每 (plan_case, device_model) 一行 |
| 评论/附件 | comment / attachment | 通过 target_type + target_id 聚合 |
| 标签 | tag + tag_map | 通用关联 |

