"""REST endpoints for querying legacy test data."""
from __future__ import annotations

from flask import Blueprint, request

from services.legacy_data_service import LegacyDataService
from utils.exceptions import BizError
from utils.response import json_response


legacy_data_bp = Blueprint("legacy_data", __name__, url_prefix="/api/legacy-data")


@legacy_data_bp.errorhandler(BizError)
def _handle_biz_error(err: BizError):
    return json_response(code=err.code, message=err.message, data=err.data), err.code


@legacy_data_bp.get("/projects")
def get_projects():
    keyword = request.args.get("keyword")
    projects = LegacyDataService.list_projects(keyword)
    return json_response(data=projects)


@legacy_data_bp.get("/plans")
def get_plans():
    project_name = request.args.get("project_name")
    if not project_name:
        raise BizError(message="project_name 参数必填", code=400)
    keyword = request.args.get("keyword")
    plans = LegacyDataService.list_plans(project_name, keyword)
    return json_response(data=plans)


@legacy_data_bp.get("/plans/<int:plan_id>/models")
def get_models(plan_id: int):
    models = LegacyDataService.list_models(plan_id)
    return json_response(data=models)


@legacy_data_bp.get("/plans/<int:plan_id>/statistics")
def get_plan_statistics(plan_id: int):
    statistics = LegacyDataService.get_plan_statistics(plan_id)
    return json_response(data=statistics)


@legacy_data_bp.get("/plans/<int:plan_id>/sheets")
def get_sheets(plan_id: int):
    sheets = LegacyDataService.list_sheets(plan_id)
    return json_response(data=sheets)


@legacy_data_bp.get("/sheets/<int:sheet_id>/cases")
def get_cases(sheet_id: int):
    model_id = request.args.get("model_id", type=int)
    if model_id is None:
        raise BizError(message="model_id 参数必填", code=400)
    cases = LegacyDataService.list_case_status(model_id, sheet_id)
    return json_response(data=cases)


@legacy_data_bp.get("/images")
def get_images():
    raw_ids = request.args.getlist("execution_ids")
    execution_ids: list[int] = []
    for raw in raw_ids:
        if not raw:
            continue
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        for part in parts:
            try:
                execution_ids.append(int(part))
            except ValueError:
                raise BizError(message=f"execution_id '{part}' 非法", code=400)
    images = LegacyDataService.list_images(execution_ids, request.host_url)
    return json_response(data=images)
