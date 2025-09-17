# -*- coding: utf-8 -*-
"""测试计划相关接口"""

from flask import Blueprint, request

from constants.roles import Role
from constants.test_plan import validate_plan_status
from controllers.auth_helpers import auth_required
from services.test_plan_service import TestPlanService
from utils.permissions import get_current_user
from utils.response import json_response
from utils.exceptions import BizError


test_plan_bp = Blueprint("test_plan", __name__, url_prefix="/api/test-plans")


@test_plan_bp.errorhandler(BizError)
def _handle_biz_error(err: BizError):
    return json_response(code=err.code, message=err.message, data=err.data), err.code


@test_plan_bp.post("")
@auth_required(roles=[Role.ADMIN, Role.DEPT_ADMIN, Role.PROJECT_ADMIN])
def create_test_plan():
    payload = request.get_json(silent=True) or {}
    current_user = get_current_user()
    plan = TestPlanService.create(
        current_user=current_user,
        project_id=payload.get("project_id"),
        name=payload.get("name", ""),
        description=payload.get("description"),
        status=payload.get("status"),
        start_date=payload.get("start_date"),
        end_date=payload.get("end_date"),
        case_ids=payload.get("case_ids"),
        case_group_ids=payload.get("case_group_ids"),
        single_execution_case_ids=payload.get("single_execution_case_ids"),
        device_model_ids=payload.get("device_model_ids"),
        tester_user_ids=payload.get("tester_user_ids"),
    )
    return json_response(message="创建成功", data=plan.to_dict())


@test_plan_bp.get("")
@auth_required()
def list_test_plans():
    args = request.args
    status = args.get("status")
    if status:
        validate_plan_status(status)
    items, total = TestPlanService.list(
        project_id=args.get("project_id", type=int),
        status=status,
        keyword=args.get("keyword"),
        page=args.get("page", type=int, default=1),
        page_size=args.get("page_size", type=int, default=20),
        order_desc=args.get("order", default="desc").lower() != "asc",
    )
    return json_response(
        data={
            "items": [plan.to_dict(include_cases=False, include_runs=False) for plan in items],
            "total": total,
        }
    )


@test_plan_bp.get("/<int:plan_id>")
@auth_required()
def get_test_plan(plan_id: int):
    plan = TestPlanService.get(plan_id)
    return json_response(data=plan.to_dict())


@test_plan_bp.put("/<int:plan_id>")
@auth_required(roles=[Role.ADMIN, Role.DEPT_ADMIN, Role.PROJECT_ADMIN])
def update_test_plan(plan_id: int):
    payload = request.get_json(silent=True) or {}
    current_user = get_current_user()
    plan = TestPlanService.update(
        plan_id,
        current_user=current_user,
        name=payload.get("name"),
        description=payload.get("description"),
        status=payload.get("status"),
        start_date=payload.get("start_date"),
        end_date=payload.get("end_date"),
    )
    return json_response(message="更新成功", data=plan.to_dict())


@test_plan_bp.delete("/<int:plan_id>")
@auth_required(roles=[Role.ADMIN, Role.DEPT_ADMIN, Role.PROJECT_ADMIN])
def delete_test_plan(plan_id: int):
    current_user = get_current_user()
    TestPlanService.delete(plan_id, current_user=current_user)
    return json_response(message="删除成功")


@test_plan_bp.post("/<int:plan_id>/results")
@auth_required()
def record_test_plan_result(plan_id: int):
    payload = request.get_json(silent=True) or {}
    current_user = get_current_user()
    result = TestPlanService.record_result(
        plan_id,
        current_user=current_user,
        plan_case_id=payload.get("plan_case_id"),
        result=payload.get("result"),
        device_model_id=payload.get("device_model_id"),
        remark=payload.get("remark"),
        failure_reason=payload.get("failure_reason"),
        bug_ref=payload.get("bug_ref"),
        duration_ms=payload.get("duration_ms"),
    )
    return json_response(message="结果已记录", data=result.to_dict())
