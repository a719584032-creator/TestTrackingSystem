# -*- coding: utf-8 -*-
"""constants/test_plan.py
--------------------------------------------------------------------
测试计划与执行结果相关的枚举常量。

目前的业务约束：
- 测试计划状态遵循产品原型给出的六种状态。
- 执行结果状态支持 pending / pass / fail / block / skip。
- 为便于服务层校验，提供 values() 及 validate_* 辅助函数。
"""

from enum import Enum
from typing import Iterable

from utils.exceptions import BizError


class TestPlanStatus(Enum):
    """测试计划状态枚举。"""

    ACTIVE = "active"
    PENDING = "pending"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    INACTIVE = "inactive"

    @classmethod
    def values(cls) -> list[str]:
        return [m.value for m in cls]


DEFAULT_PLAN_STATUS = TestPlanStatus.PENDING.value


class ExecutionResultStatus(Enum):
    """计划内单条执行结果的状态枚举。"""

    PENDING = "pending"
    PASS = "pass"
    FAIL = "fail"
    BLOCK = "block"
    SKIP = "skip"

    @classmethod
    def values(cls) -> list[str]:
        return [m.value for m in cls]


def validate_plan_status(status: str):
    if status not in TestPlanStatus.values():
        raise BizError(f"测试计划状态必须是 {TestPlanStatus.values()} 之一", 400)


def validate_plan_statuses(status_list: Iterable[str]):
    for status in status_list:
        validate_plan_status(status)


def validate_execution_result_status(result: str):
    if result not in ExecutionResultStatus.values():
        raise BizError(f"执行结果状态必须是 {ExecutionResultStatus.values()} 之一", 400)


def validate_final_execution_status(result: str):
    """最终录入结果仅允许 pass/fail/block/skip，不允许 pending。"""

    allowed = {
        ExecutionResultStatus.PASS.value,
        ExecutionResultStatus.FAIL.value,
        ExecutionResultStatus.BLOCK.value,
        ExecutionResultStatus.SKIP.value,
    }
    if result not in allowed:
        raise BizError("执行结果必须是 pass/fail/block/skip 之一", 400)
