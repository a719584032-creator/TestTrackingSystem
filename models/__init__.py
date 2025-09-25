# -*- coding: utf-8 -*-
"""
__init__.py
--------------------------------------------------------------------
汇总导入所有模型，使得：
- Flask-Migrate/Alembic 自动检测模型。
- 外部模块可简化引用：from models import TestCase, ExecutionRun
注意：
- 避免循环导入：各模型仅在这里集中 import。
- 若模型特别多，可分批导入或动态发现（当前规模够用）。
"""

from .mixins import TimestampMixin
from .user import User
from .department import Department, DepartmentMember
from .project import Project, ProjectMember
from .device_model import DeviceModel
from .case_group import CaseGroup
from .test_case_history import TestCaseHistory
from .test_case import TestCase
from .test_plan import TestPlan
from .plan_case import PlanCase
from .plan_device_model import PlanDeviceModel
from .plan_tester import TestPlanTester
from .execution import (
    ExecutionRun,
    ExecutionResult,
    ExecutionResultLog,
    EXECUTION_RESULT_ATTACHMENT_TYPE,
    EXECUTION_RESULT_LOG_ATTACHMENT_TYPE,
)
from .comment import Comment
from .attachment import Attachment
from .tag import Tag, TagMap
from .user_password_history import UserPasswordHistory

all = [
    "TimestampMixin",
    "User", "Department", "DepartmentMember", "Project", "ProjectMember",
    "DeviceModel", "CaseGroup", "TestCaseHistory", "TestCase", "TestPlan",
    "PlanCase", "PlanDeviceModel", "TestPlanTester", "ExecutionRun", "ExecutionResult",
    "ExecutionResultLog",
    "EXECUTION_RESULT_ATTACHMENT_TYPE",
    "EXECUTION_RESULT_LOG_ATTACHMENT_TYPE",
    "Comment", "Attachment", "Tag", "TagMap", "UserPasswordHistory"
]
