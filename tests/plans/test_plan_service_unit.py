# -*- coding: utf-8 -*-
"""单元测试：验证测试计划服务层新增能力。"""

from __future__ import annotations

import uuid

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


def _create_plan() -> TestPlan:
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
    return plan


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
