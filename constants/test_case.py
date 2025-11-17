# constants/test_case.py
"""
测试用例相关的枚举与常量集合
统一管理：
  - 优先级 Priority: P0 / P1 / P2 / P3
  - 状态 Status: active / deprecated
  - 类型 Case Type: functional / ...（可扩展）
提供:
  - Enum 定义（更清晰、可读性好）
  - values() 方法：返回所有 value 列表
  - 校验辅助函数
"""

from enum import Enum
from typing import Iterable
from utils.exceptions import BizError


class TestCasePriority(Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

    @classmethod
    def values(cls):
        return [m.value for m in cls]


class TestCaseStatus(Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"

    @classmethod
    def values(cls):
        return [m.value for m in cls]


class TestCaseType(Enum):
    FUNCTIONAL = "functional"
    PERFORMANCE = "performance"
    API = "api"

    @classmethod
    def values(cls):
        return [m.value for m in cls]


# -------- 校验辅助函数 --------
def validate_priority(priority: str):
    if priority not in TestCasePriority.values():
        raise BizError(f"优先级必须是 {TestCasePriority.values()} 之一", 400)


def validate_status(status: str):
    if status not in TestCaseStatus.values():
        raise BizError(f"状态必须是 {TestCaseStatus.values()} 之一", 400)


def validate_case_type(case_type: str):
    if case_type not in TestCaseType.values():
        raise BizError(f"用例类型必须是 {TestCaseType.values()} 之一", 400)


def validate_test_case_fields(
        *,
        priority: str = None,
        status: str = None,
        case_type: str = None,
        skip_none: bool = True
):
    """
    统一校验多个字段
    :param skip_none: True 时 None 值跳过校验
    """
    if priority is not None or not skip_none:
        validate_priority(priority)
    if status is not None or not skip_none:
        validate_status(status)
    if case_type is not None or not skip_none:
        validate_case_type(case_type)
