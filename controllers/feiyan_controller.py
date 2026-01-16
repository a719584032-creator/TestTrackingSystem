# -*- coding: utf-8 -*-
"""飞雁数据导入导出接口。"""

from __future__ import annotations

from io import BytesIO
from typing import Dict, List, Optional

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
    page_size = min(page_size, 1000)

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

    group_paths = FeiyanService.list_case_group_paths(
        plan_id_ext=plan_id,
        keyword=keyword,
        group_path=group_path,
        priority=priority,
        run_result=run_result,
    )

    def _normalize_group_path(raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        value = str(raw).strip().strip("/")
        return value or None

    def _build_group_tree(paths: List[Optional[str]]) -> Dict:
        normalized_paths = set()
        for raw in paths:
            normalized = _normalize_group_path(raw)
            if normalized:
                normalized_paths.add(normalized)
        root = {"name": "root", "path": "root", "children": []}
        node_map = {"root": root}
        for path in sorted(normalized_paths):
            parts = [part for part in path.split("/") if part]
            if not parts:
                continue
            if parts[0] != "root":
                parts = ["root"] + parts
            parent = root
            current_path = "root"
            for part in parts[1:]:
                current_path = f"{current_path}/{part}"
                node = node_map.get(current_path)
                if not node:
                    node = {"name": part, "path": current_path, "children": []}
                    node_map[current_path] = node
                    parent["children"].append(node)
                parent = node

        def _sort_children(node: Dict):
            node["children"].sort(key=lambda item: item["path"])
            for child in node["children"]:
                _sort_children(child)

        _sort_children(root)
        return root

    group_tree = _build_group_tree(group_paths)

    payload_items = [
        FeiyanService.enrich_case_payload(item.to_dict())
        for item in items
    ]

    return json_response(
        data={
            "items": payload_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "group_tree": group_tree,
        }
    )


@feiyan_bp.post("/test-plans/<plan_id>/attachments/presign")
@auth_required()
def presign_test_plan_attachment(plan_id: str):
    payload = request.get_json(silent=True) or {}
    result = FeiyanService.create_attachment_presign(
        plan_id_ext=plan_id,
        case_id_ext=payload.get("case_id") or payload.get("case_id_ext"),
        file_name=payload.get("file_name") or payload.get("name") or payload.get("filename"),
        mime_type=payload.get("mime_type") or payload.get("content_type"),
        size=payload.get("size"),
    )
    return json_response(data=result)


@feiyan_bp.post("/test-plans/<plan_id>/results")
@auth_required()
def record_test_plan_result(plan_id: str):
    if request.files:
        raise BizError("请先使用对象存储上传附件", 400)
    payload = request.get_json(silent=True) or {}
    current_user = get_current_user()

    run_result = payload.get("run_result")
    case_result = FeiyanService.record_result(plan_id, payload, current_user=current_user)
    message = "结果已记录"
    if run_result is None or (isinstance(run_result, str) and not run_result.strip()):
        message = "结果为空，未更新"

    response_payload = FeiyanService.enrich_case_payload(case_result.to_dict())
    return json_response(message=message, data=response_payload)


@feiyan_bp.post("/test-plans/import")
@auth_required()
def import_test_plans():
    if not request.files:
        raise BizError("导入文件不能为空", 400)
    file_storage = request.files.get("file")
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
