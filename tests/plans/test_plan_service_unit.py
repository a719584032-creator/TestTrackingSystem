# -*- coding: utf-8 -*-
"""单元测试：验证测试计划服务层新增能力。"""

from __future__ import annotations

import base64
import calendar
import hashlib
import hmac
import uuid
from datetime import datetime

import pytest

from app import create_app
from extensions.database import db
from models import (
    Department,
    DepartmentMember,
    DeviceModel,
    Project,
    TestCase,
    TestPlan,
    User,
)
from services.test_plan_service import TestPlanService
from utils.exceptions import BizError


@pytest.fixture()
def app_context():
    """提供测试用的 Flask 应用上下文（使用内存数据库）。"""

    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _random_text(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _bootstrap_plan_environment() -> dict[str, object]:
    """创建测试计划所需的基础数据。"""

    department = Department(name=_random_text("Dept"), code=_random_text("D"))
    db.session.add(department)

    project = Project(
        department=department,
        name=_random_text("Project"),
        code=_random_text("PRJ"),
    )
    db.session.add(project)

    device = DeviceModel(
        department=department,
        name=_random_text("Device"),
        category="headset",
        model_code=_random_text("MDL"),
    )
    db.session.add(device)

    case = TestCase(
        department=department,
        title=_random_text("Case"),
        steps=[{"no": 1, "action": "step", "expected": "result"}],
        expected_result="result",
        keywords=[],
        priority="P1",
    )
    db.session.add(case)

    tester_a = User(username=_random_text("tester"), password_hash="hash", role="user")
    tester_b = User(username=_random_text("tester"), password_hash="hash", role="user")
    db.session.add_all([tester_a, tester_b])

    db.session.flush()

    db.session.add_all(
        [
            DepartmentMember(department_id=department.id, user_id=tester_a.id),
            DepartmentMember(department_id=department.id, user_id=tester_b.id),
        ]
    )

    db.session.flush()

    return {
        "department": department,
        "project": project,
        "device": device,
        "case": case,
        "tester_a": tester_a,
        "tester_b": tester_b,
    }


def _create_plan_with_env() -> tuple[TestPlan, dict[str, object]]:
    env = _bootstrap_plan_environment()
    plan = TestPlanService.create(
        current_user=None,
        project_id=env["project"].id,
        name=_random_text("Plan"),
        description="demo",
        status="active",
        case_ids=[env["case"].id],
        case_group_ids=[],
        single_execution_case_ids=[],
        device_model_ids=[env["device"].id],
        tester_user_ids=[env["tester_a"].id, env["tester_b"].id],
    )
    return plan, env


def _create_plan() -> TestPlan:
    plan, _ = _create_plan_with_env()
    return plan


def _encode_execution_timestamp(app, dt: datetime) -> str:
    secret_key = app.config.get("SECRET_KEY", "")
    millis = int(calendar.timegm(dt.utctimetuple()) * 1000 + dt.microsecond / 1000)
    timestamp_part = str(millis)
    signature = hmac.new(
        secret_key.encode("utf-8"), timestamp_part.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    token = f"{timestamp_part}.{signature}".encode("utf-8")
    return base64.urlsafe_b64encode(token).decode("utf-8")


def test_device_snapshot_and_name_fields(app_context):
    """机型需要做快照，并在详情中返回名称。"""

    plan = _create_plan()
    device_name = plan.plan_device_models[0].snapshot_name

    # 修改原始机型名称不应影响计划中的快照名称
    plan.plan_device_models[0].device_model.name = "updated-name"
    db.session.commit()

    refreshed = TestPlanService.get(plan.id)
    device_entries = refreshed.to_dict()["device_models"]

    assert device_entries[0]["name"] == device_name
    # 同时返回 tester 名称方便前端展示
    tester_names = {item["name"] for item in refreshed.to_dict()["testers"]}
    expected_names = {t.tester.username for t in refreshed.plan_testers}
    assert tester_names == expected_names


def test_list_supports_department_filter(app_context):
    """列表接口支持按部门过滤。"""

    first_plan = _create_plan()
    first_department_id = first_plan.project.department_id

    second_plan = _create_plan()

    items, total = TestPlanService.list(department_id=first_department_id)
    item_ids = {item.id for item in items}

    assert total == 1
    assert item_ids == {first_plan.id}
    assert second_plan.id not in item_ids


def test_update_plan_allows_modifying_testers(app_context):
    """编辑测试计划时可调整执行人列表。"""

    plan = _create_plan()
    department_id = plan.project.department_id

    # 新增一名同部门测试人员
    extra_user = User(username=_random_text("tester"), password_hash="hash", role="user")
    db.session.add(extra_user)
    db.session.flush()
    db.session.add(DepartmentMember(department_id=department_id, user_id=extra_user.id))
    db.session.flush()

    keep_user_id = plan.plan_testers[0].user_id
    updated = TestPlanService.update(
        plan.id,
        current_user=None,
        tester_user_ids=[keep_user_id, extra_user.id],
    )

    tester_ids = {tester.user_id for tester in updated.plan_testers}
    assert tester_ids == {keep_user_id, extra_user.id}


def test_record_result_requires_encrypted_times(app_context):
    plan, env = _create_plan_with_env()
    tester = env["tester_a"]
    device = env["device"]

    # 刚创建的计划会附带一个默认执行批次及结果记录
    plan = TestPlanService.get(plan.id)
    plan_case = plan.plan_cases[0]

    end_token = _encode_execution_timestamp(app_context, datetime(2024, 1, 1, 0, 10, 0))

    with pytest.raises(BizError) as excinfo:
        TestPlanService.record_result(
            plan.id,
            current_user=tester,
            plan_case_id=plan_case.id,
            result="pass",
            device_model_id=device.id,
            execution_start_time=None,
            execution_end_time=end_token,
        )
    assert "不能为空" in str(excinfo.value)

    with pytest.raises(BizError):
        TestPlanService.record_result(
            plan.id,
            current_user=tester,
            plan_case_id=plan_case.id,
            result="pass",
            device_model_id=device.id,
            execution_start_time="  ",
            execution_end_time=end_token,
        )

    start_token = _encode_execution_timestamp(app_context, datetime(2024, 1, 1, 0, 0, 0))
    end_token = _encode_execution_timestamp(app_context, datetime(2024, 1, 1, 0, 5, 0))

    result = TestPlanService.record_result(
        plan.id,
        current_user=tester,
        plan_case_id=plan_case.id,
        result="pass",
        device_model_id=device.id,
        execution_start_time=start_token,
        execution_end_time=end_token,
    )

    assert result.execution_start_time is not None
    assert result.execution_end_time is not None
    assert result.duration_ms == 5 * 60 * 1000
