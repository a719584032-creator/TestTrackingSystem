# controllers/test_case_controller.py
from flask import Blueprint, request, g
from typing import List
from utils.response import json_response
from utils.exceptions import BizError
from services.test_case_service import TestCaseService
from controllers.auth_helpers import auth_required
from utils.permissions import get_current_user, assert_user_in_department
test_case_bp = Blueprint("test_case", __name__, url_prefix="/api/test-cases")


@test_case_bp.errorhandler(BizError)
def _biz_error(e: BizError):
    return json_response(code=e.code, message=e.message), e.code


@test_case_bp.post("")
@auth_required()
def create_test_case():
    """创建测试用例"""
    user = get_current_user()
    data = request.get_json() or {}
    # 必填参数
    department_id = data.get("department_id")
    if not department_id:
        return json_response(code=400, message="部门ID不能为空")

    title = data.get("title")
    if not title:
        return json_response(code=400, message="用例标题不能为空")
    # 必须属于当前部门
    assert_user_in_department(department_id, user)

    # 可选参数
    preconditions = data.get("preconditions")
    steps = data.get("steps", [])
    expected_result = data.get("expected_result")
    keywords = data.get("keywords", [])
    priority = data.get("priority", "P2")
    case_type = data.get("case_type", "functional")
    project_ids = data.get("project_ids", [])
    group_mappings = data.get("group_mappings", {})

    # 转换group_mappings的key为int
    if group_mappings:
        group_mappings = {
            int(k): v for k, v in group_mappings.items()
        }

    test_case = TestCaseService.create(
        department_id=department_id,
        title=title,
        preconditions=preconditions,
        steps=steps,
        expected_result=expected_result,
        keywords=keywords,
        priority=priority,
        case_type=case_type,
        created_by=user.id,
        project_ids=project_ids,
        group_mappings=group_mappings
    )

    return json_response(
        message="创建成功",
        data={
            "id": test_case.id,
            "title": test_case.title,
            "department_id": test_case.department_id,
            "priority": test_case.priority,
            "status": test_case.status,
            "created_at": test_case.created_at.isoformat()
        }
    )


@test_case_bp.get("/<int:case_id>")
@auth_required()
def get_test_case(case_id: int):
    """获取测试用例详情"""
    user = get_current_user()
    test_case = TestCaseService.get(case_id, user)

    # 构建返回数据
    data = {
        "id": test_case.id,
        "department_id": test_case.department_id,
        "title": test_case.title,
        "preconditions": test_case.preconditions,
        "steps": test_case.steps,
        "expected_result": test_case.expected_result,
        "keywords": test_case.keywords,
        "priority": test_case.priority,
        "status": test_case.status,
        "case_type": test_case.case_type,
        "created_by": test_case.created_by,
        "updated_by": test_case.updated_by,
        "created_at": test_case.created_at.isoformat() if test_case.created_at else None,
        "updated_at": test_case.updated_at.isoformat() if test_case.updated_at else None,
    }

    # 添加创建者和更新者信息
    if test_case.creator:
        data["creator"] = {
            "id": test_case.creator.id,
            "username": test_case.creator.username
        }

    if test_case.updater:
        data["updater"] = {
            "id": test_case.updater.id,
            "username": test_case.updater.username
        }

    # 添加关联的项目信息
    if test_case.project_links:
        data["projects"] = [
            {
                "project_id": link.project_id,
                "group_id": link.group_id,
                "order_no": link.order_no
            }
            for link in test_case.project_links
        ]

    return json_response(data=data)


@test_case_bp.put("/<int:case_id>")
@auth_required()
def update_test_case(case_id: int):
    """更新测试用例"""
    user = get_current_user()
    data = request.get_json() or {}

    # 提取可更新的字段
    update_fields = {}

    if "title" in data:
        update_fields["title"] = data["title"]
    if "preconditions" in data:
        update_fields["preconditions"] = data["preconditions"]
    if "steps" in data:
        update_fields["steps"] = data["steps"]
    if "expected_result" in data:
        update_fields["expected_result"] = data["expected_result"]
    if "keywords" in data:
        update_fields["keywords"] = data["keywords"]
    if "priority" in data:
        update_fields["priority"] = data["priority"]
    if "status" in data:
        update_fields["status"] = data["status"]
    if "case_type" in data:
        update_fields["case_type"] = data["case_type"]

    test_case = TestCaseService.update(
        case_id=case_id,
        user=user,
        **update_fields
    )

    return json_response(
        message="更新成功",
        data={
            "id": test_case.id,
            "title": test_case.title,
            "updated_at": test_case.updated_at.isoformat()
        }
    )


@test_case_bp.delete("/<int:case_id>")
@auth_required()
def delete_test_case(case_id: int):
    """删除测试用例"""
    user = get_current_user()
    success = TestCaseService.delete(case_id, user)

    if success:
        return json_response(message="删除成功")
    else:
        return json_response(code=500, message="删除失败")


@test_case_bp.get("/department/<int:department_id>")
@auth_required()
def list_test_cases(department_id: int):
    """获取部门的测试用例列表"""
    user = get_current_user()
    assert_user_in_department(department_id, user)

    # 获取查询参数
    args = request.args
    title = args.get("title")
    status = args.get("status", "active")
    priority = args.get("priority")
    case_type = args.get("case_type")
    keywords = args.getlist("keywords")
    project_id = args.get("project_id", type=int)
    group_id = args.get("group_id", type=int)
    page = args.get("page", 1, type=int)
    page_size = args.get("page_size", 20, type=int)
    order_by = args.get("order_by", "created_at")
    order_desc = args.get("order_desc", "true").lower() == "true"

    # 限制page_size
    page_size = min(page_size, 100)

    test_cases, total = TestCaseService.list(
        department_id=department_id,
        title=title,
        status=status,
        priority=priority,
        case_type=case_type,
        keywords=keywords,
        project_id=project_id,
        group_id=group_id,
        page=page,
        page_size=page_size,
        order_by=order_by,
        order_desc=order_desc
    )

    # 构建返回数据
    items = []
    for tc in test_cases:
        item = {
            "id": tc.id,
            "title": tc.title,
            "priority": tc.priority,
            "status": tc.status,
            "case_type": tc.case_type,
            "keywords": tc.keywords,
            "created_at": tc.created_at.isoformat() if tc.created_at else None,
            "updated_at": tc.updated_at.isoformat() if tc.updated_at else None,
        }

        # 添加创建者信息
        if tc.creator:
            item["creator"] = {
                "id": tc.creator.id,
                "username": tc.creator.username
            }

        items.append(item)

    return json_response(data={
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    })


@test_case_bp.delete("/batch")
@auth_required()
def batch_delete_test_cases():
    """批量删除测试用例"""
    user = get_current_user()
    data = request.get_json() or {}

    case_ids = data.get("case_ids", [])
    department_id = data.get("department_id")

    if not case_ids:
        return json_response(code=400, message="请选择要删除的用例")

    if not department_id:
        return json_response(code=400, message="部门ID不能为空")

    assert_user_in_department(department_id, user)

    deleted_count = TestCaseService.batch_delete(
        case_ids=case_ids,
        department_id=department_id,
    )

    return json_response(
        message=f"成功删除{deleted_count}个用例"
    )

