# -*- coding: utf-8 -*-
"""飞雁数据导入导出接口。"""

from __future__ import annotations

from io import BytesIO

from flask import Blueprint, request, send_file

from controllers.auth_helpers import auth_required
from services.feiyan_service import FeiyanService
from utils.exceptions import BizError
from utils.permissions import get_current_user
from utils.response import json_response


feiyan_bp = Blueprint("feiyan", __name__, url_prefix="/api/feiyan")


@feiyan_bp.errorhandler(BizError)
def _handle_biz_error(err: BizError):
    return json_response(code=err.code, message=err.message, data=err.data), err.code


@feiyan_bp.get("/departments")
@auth_required()
def list_departments():
    args = request.args
    page = args.get("page", type=int, default=1)
    page_size = args.get("page_size", type=int, default=1000)
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 1
    page_size = min(page_size, 1000)

    items, total = FeiyanService.list_departments(page, page_size)
    return json_response(
        data={"items": items, "total": total, "page": page, "page_size": page_size}
    )


@feiyan_bp.get("/test-plans")
@auth_required()
def list_test_plans():
    args = request.args
    page = args.get("page", type=int, default=1)
    page_size = args.get("page_size", type=int, default=100)
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 1
    page_size = min(page_size, 1000)

    dept_id = args.get("department_id") or args.get("dept_id")
    project_id = args.get("project_id")

    items, total = FeiyanService.list_test_plans(
        dept_id_ext=dept_id,
        project_id_ext=project_id,
        page=page,
        page_size=page_size,
    )

    return json_response(
        data={
            "items": [plan.to_dict() for plan in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@feiyan_bp.get("/test-plans/<plan_id>/cases")
@auth_required()
def list_test_plan_cases(plan_id: str):
    args = request.args
    page = args.get("page", type=int, default=1)
    page_size = args.get("page_size", type=int, default=100)
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 1
    page_size = min(page_size, 2000)

    keyword = args.get("title") or args.get("keyword")
    group_path = args.get("group_path") or args.get("group")
    priority = args.get("priority")
    run_result = args.get("run_result") or args.get("result") or args.get("status")

    items, total = FeiyanService.list_cases(
        plan_id_ext=plan_id,
        keyword=keyword,
        group_path=group_path,
        priority=priority,
        run_result=run_result,
        page=page,
        page_size=page_size,
    )

    return json_response(
        data={
            "items": [item.to_dict() for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@feiyan_bp.post("/test-plans/<plan_id>/results")
@auth_required()
def record_test_plan_result(plan_id: str):
    payload = request.get_json(silent=True) or {}
    current_user = get_current_user()

    run_result = payload.get("run_result")
    case_result = FeiyanService.record_result(plan_id, payload, current_user=current_user)
    message = "结果已记录"
    if run_result is None or (isinstance(run_result, str) and not run_result.strip()):
        message = "结果为空，未更新"

    return json_response(message=message, data=case_result.to_dict())


@feiyan_bp.post("/test-plans/import")
@auth_required()
def import_test_plans():
    if not request.files:
        raise BizError("导入文件不能为空", 400)
    file_storage = request.files.get("file")
    if not file_storage:
        files = request.files.getlist("files")
        if files:
            file_storage = files[0]
    if not file_storage or not file_storage.filename:
        raise BizError("导入文件不能为空", 400)

    current_user = get_current_user()
    result = FeiyanService.import_excel(file_storage.read(), current_user=current_user)
    return json_response(message="导入完成", data=result)


@feiyan_bp.get("/test-plans/<plan_id>/export")
@auth_required()
def export_test_plan(plan_id: str):
    payload = FeiyanService.export_plan(plan_id)
    filename = f"feiyan_test_plan_{plan_id}.xlsx"
    return send_file(
        BytesIO(payload),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )
