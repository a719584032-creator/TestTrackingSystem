# controllers/test_case_controller.py

from flask import Blueprint, request
from typing import Any, Dict, List
from utils.response import json_response
from utils.exceptions import BizError
from services.test_case_service import TestCaseService
from controllers.auth_helpers import auth_required
from utils.permissions import get_current_user, assert_user_in_department
from repositories.test_case_repository import TestCaseRepository, TestCaseHistoryRepository
from extensions.database import db
from services.case_group_service import CaseGroupService
from controllers.up_files import parse_excel_cases


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

    # 验证用户权限
    assert_user_in_department(department_id, user)

    # 可选参数
    preconditions = data.get("preconditions")
    steps = data.get("steps", [])
    expected_result = data.get("expected_result")
    keywords = data.get("keywords", [])
    priority = data.get("priority", "P2")
    case_type = data.get("case_type", "functional")
    group_id = data.get("group_id")
    workload_minutes = data.get("workload_minutes")

    # 创建用例
    test_case = TestCaseService.create(
        department_id=department_id,
        title=title,
        created_by=user.id,
        preconditions=preconditions,
        steps=steps,
        expected_result=expected_result,
        keywords=keywords,
        priority=priority,
        case_type=case_type,
        group_id=group_id,
        workload_minutes=workload_minutes
    )

    return json_response(
        message="创建成功",
        data={
            "id": test_case.id,
            "title": test_case.title,
            "department_id": test_case.department_id,
            "group_id": test_case.group_id,
            "priority": test_case.priority,
            "status": test_case.status,
            "case_type": test_case.case_type,
            "version": test_case.version,
            "created_at": test_case.created_at.isoformat()
        }
    )


@test_case_bp.post("/batch-import")
@auth_required()
def batch_import_test_cases():
    """批量导入测试用例"""
    user = get_current_user()
    if request.files:
        return _batch_import_test_cases_from_file(user)

    data = request.get_json() or {}

    department_id = data.get("department_id")
    if not department_id:
        return json_response(code=400, message="部门ID不能为空")

    cases_data = data.get("cases")
    if not isinstance(cases_data, list) or not cases_data:
        return json_response(code=400, message="导入的用例数据不能为空")

    assert_user_in_department(department_id, user)

    result = TestCaseService.batch_import(
        department_id=department_id,
        cases_data=cases_data,
        user=user
    )

    return _build_batch_import_response(cases_data, result)


def _batch_import_test_cases_from_file(user):
    form = request.form

    department_id_raw = form.get("department_id")
    try:
        department_id = int(department_id_raw)
    except (TypeError, ValueError):
        return json_response(code=400, message="部门ID不能为空")

    assert_user_in_department(department_id, user)

    file_storage = request.files.get("file")
    if not file_storage or file_storage.filename == "":
        return json_response(code=400, message="导入文件不能为空")

    file_bytes = file_storage.read()
    if not file_bytes:
        return json_response(code=400, message="导入文件不能为空")

    sheet_index = 0
    # 暂时不支持指定sheet
    # sheet_index_raw = form.get("sheet_index")
    # if sheet_index_raw not in (None, ""):
    #     try:
    #         sheet_index = int(sheet_index_raw)
    #     except (TypeError, ValueError):
    #         return json_response(code=400, message="sheet_index参数不合法")

    try:
        folder_name, parsed_cases = parse_excel_cases(file_bytes, sheet=sheet_index)
    except Exception as exc:  # pragma: no cover - 防御性兜底
        raise BizError(f"解析Excel失败: {exc}", 400)

    if not parsed_cases:
        raise BizError("Excel中未解析到任何用例", 400)

    group_id_raw = form.get("group_id")
    parent_group = None
    if group_id_raw not in (None, ""):
        try:
            parent_group_id = int(group_id_raw)
        except (TypeError, ValueError):
            return json_response(code=400, message="目录ID不合法")
        parent_group = CaseGroupService.get(parent_group_id, user)
        if parent_group.department_id != department_id:
            return json_response(code=400, message="所选目录不属于该部门")

    target_group = parent_group
    folder_name = (folder_name or "").strip()
    if folder_name:
        parent_id = parent_group.id if parent_group else None
        target_group = CaseGroupService.get_or_create_by_name(
            department_id=department_id,
            name=folder_name,
            user=user,
            parent_id=parent_id
        )

    resolved_group_id = target_group.id if target_group else None

    cases_data: List[Dict[str, Any]] = []
    for case in parsed_cases:
        cases_data.append({
            "department_id": department_id,
            "group_id": resolved_group_id,
            "title": case.get("title"),
            "preconditions": case.get("preconditions"),
            "steps": case.get("steps") or [],
            "expected_result": case.get("expected_result"),
            "keywords": case.get("keywords") or [],
        })

    result = TestCaseService.batch_import(
        department_id=department_id,
        cases_data=cases_data,
        user=user
    )

    return _build_batch_import_response(cases_data, result)


def _build_batch_import_response(cases_data: List[Dict[str, Any]], result: Dict[str, Any]):
    success_items = []
    for case in result["created"]:
        success_items.append({
            "id": case.id,
            "title": case.title,
            "department_id": case.department_id,
            "group_id": case.group_id,
            "priority": case.priority,
            "case_type": case.case_type,
            "status": case.status,
            "version": case.version,
            "created_at": case.created_at.isoformat() if case.created_at else None
        })

    failures = result["errors"]
    total = len(cases_data)
    success_count = len(success_items)
    failure_count = len(failures)

    return json_response(
        message=f"成功导入{success_count}条, 失败{failure_count}条",
        data={
            "total": total,
            "success_count": success_count,
            "failure_count": failure_count,
            "success": success_items,
            "failures": failures
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
        "group_id": test_case.group_id,
        "title": test_case.title,
        "preconditions": test_case.preconditions,
        "steps": test_case.steps,
        "expected_result": test_case.expected_result,
        "keywords": test_case.keywords,
        "priority": test_case.priority,
        "status": test_case.status,
        "case_type": test_case.case_type,
        "workload_minutes": test_case.workload_minutes,
        "version": test_case.version,
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

    # 添加分组信息
    if test_case.group:
        data["group"] = {
            "id": test_case.group.id,
            "name": test_case.group.name,
            "path": test_case.group.path
        }

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
    if "workload_minutes" in data:
        update_fields["workload_minutes"] = data["workload_minutes"]
    if "group_id" in data:
        update_fields["group_id"] = data["group_id"]

    # 更新用例
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
            "version": test_case.version,
            "updated_at": test_case.updated_at.isoformat()
        }
    )


@test_case_bp.delete("/<int:case_id>")
@auth_required()
def delete_test_case(case_id: int):
    """删除测试用例（软删除）"""
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
    status = args.get("status")
    priority = args.get("priority")
    case_type = args.get("case_type")
    keywords = args.getlist("keywords")
    group_id = args.get("group_id", type=int)
    page = args.get("page", 1, type=int)
    page_size = args.get("page_size", 20, type=int)
    order_by = args.get("order_by", "created_at")
    order_desc = args.get("order_desc", "true").lower() == "true"

    # 限制page_size
    page_size = min(page_size, 100)

    # 查询用例
    test_cases, total = TestCaseService.list(
        department_id=department_id,
        title=title,
        status=status,
        priority=priority,
        case_type=case_type,
        keywords=keywords,
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
            "workload_minutes": tc.workload_minutes,
            "version": tc.version,
            "group_id": tc.group_id,
            "created_at": tc.created_at.isoformat() if tc.created_at else None,
            "updated_at": tc.updated_at.isoformat() if tc.updated_at else None
        }

        # 添加创建者信息
        if tc.creator:
            item["creator"] = {
                "id": tc.creator.id,
                "username": tc.creator.username
            }
        # 添加更新者信息
        if tc.updater:
            item["updated_by"] = tc.updater.username

        # 添加分组信息
        if tc.group:
            item["group"] = {
                "id": tc.group.id,
                "name": tc.group.name,
                "path": tc.group.path
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

    # 执行批量删除
    deleted_count = TestCaseService.batch_delete(
        case_ids=case_ids,
        department_id=department_id,
        user=user
    )

    return json_response(
        message=f"成功删除{deleted_count}个用例"
    )


@test_case_bp.get("/<int:case_id>/history")
@auth_required()
def get_test_case_history(case_id: int):
    """获取测试用例的变更历史"""
    user = get_current_user()
    limit = request.args.get("limit", 10, type=int)
    limit = min(limit, 50)  # 最多返回50条

    histories = TestCaseService.get_history(case_id, user, limit)

    # 构建返回数据
    items = []
    for history in histories:
        item = {
            "id": history.id,
            "version": history.version,
            "change_type": history.change_type,
            "change_summary": history.change_summary,
            "changed_fields": history.changed_fields,
            "operated_at": history.operated_at.isoformat(),
            "title": history.title,
            "priority": history.priority,
            "status": history.status,
            "case_type": history.case_type,
        }

        # 添加操作人信息
        if history.operator:
            item["operator"] = {
                "id": history.operator.id,
                "username": history.operator.username
            }

        items.append(item)

    return json_response(data={
        "items": items,
        "total": len(items)
    })


@test_case_bp.post("/<int:case_id>/restore")
@auth_required()
def restore_test_case(case_id: int):
    """恢复已删除的测试用例"""
    user = get_current_user()

    # 获取已删除的用例
    test_case = TestCaseRepository.get_by_id(case_id, include_deleted=True)
    if not test_case:
        return json_response(code=404, message="测试用例不存在")

    if not test_case.is_deleted:
        return json_response(code=400, message="该用例未被删除")

    # 验证用户权限
    assert_user_in_department(test_case.department_id, user)

    # 恢复用例
    test_case.restore()
    test_case.updated_by = user.id
    test_case.increment_version()
    db.session.commit()

    # 创建历史记录
    TestCaseHistoryRepository.create_history(
        test_case=test_case,
        change_type="RESTORE",
        operated_by=user.id,
        change_summary="恢复测试用例"
    )

    return json_response(
        message="恢复成功",
        data={
            "id": test_case.id,
            "title": test_case.title,
            "version": test_case.version
        }
    )


@test_case_bp.post("/<int:case_id>/copy")
@auth_required()
def copy_test_case(case_id: int):
    """复制测试用例"""
    user = get_current_user()
    data = request.get_json() or {}

    # 获取原用例
    source_case = TestCaseService.get(case_id, user)

    # 新标题
    new_title = data.get("title", f"{source_case.title}_副本")
    target_group_id = data.get("group_id", source_case.group_id)

    # 创建副本
    new_case = TestCaseService.create(
        department_id=source_case.department_id,
        title=new_title,
        created_by=user.id,
        preconditions=source_case.preconditions,
        steps=source_case.steps,
        expected_result=source_case.expected_result,
        keywords=source_case.keywords,
        priority=source_case.priority,
        case_type=source_case.case_type,
        group_id=target_group_id,
        workload_minutes=source_case.workload_minutes
    )

    return json_response(
        message="复制成功",
        data={
            "id": new_case.id,
            "title": new_case.title,
            "group_id": new_case.group_id
        }
    )


