# -*- coding: utf-8 -*-
"""飞雁数据导入导出与执行结果服务。"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app
from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel
from sqlalchemy import case, func

from extensions.database import db
from models.feiyan_plan_case_result import FeiyanPlanCaseResult
from models.feiyan_test_plan import FeiyanTestPlan
from repositories.feiyan_plan_case_result_repository import FeiyanPlanCaseResultRepository
from repositories.feiyan_test_plan_repository import FeiyanTestPlanRepository
from utils.exceptions import BizError


HEADER_FIELD_MAP = {
    "Department.id": "dept_id_ext",
    "Department.name": "dept_name",
    "Project.id": "project_id_ext",
    "Project.name": "project_name",
    "DeviceModel.id": "device_id_ext",
    "DeviceModel.name": "device_name",
    "TestPlan.id": "plan_id_ext",
    "TestPlan.name": "plan_name",
    "PlanStatistics.total_results": "total",
    "PlanStatistics.passed": "passed",
    "PlanStatistics.failed": "failed",
    "PlanStatistics.blocked": "blocked",
    "PlanStatistics.not_run": "not_run",
    "PlanTester.id": "tester_ids",
    "PlanTester.name": "tester_names",
    "PlanExecutionRun.start_time": "plan_start_time",
    "PlanExecutionRun.end_time": "plan_end_time",
    "PlanCase.group_path": "group_path",
    "PlanCase.case_id": "case_id_ext",
    "PlanCase.title": "case_title",
    "PlanCase.priority": "priority",
    "PlanCase.target": "case_target",
    "PlanCase.preconditions": "preconditions",
    "PlanCase.steps": "steps_json",
    "PlanCase.expected_result": "expected_result",
    "PlanCase.keywords": "keywords_json",
    "PlanCase.workload_minutes": "workload_minutes",
    "CaseExecutionResult.id": "executed_by_id",
    "CaseExecutionResult.name": "executed_by_name",
    "CaseExecutionResult.start_time": "execution_start_time",
    "CaseExecutionResult.end_time": "execution_end_time",
    "CaseExecutionResult.run_result": "run_result",
    "CaseExecutionResult.remark": "remark",
    "CaseExecutionResult.failure_reason": "failure_reason",
    "CaseExecutionResult.bug_ref": "bug_ref",
    "CaseExecutionResult.files": "attachments_json",
}

PLAN_FIELDS = {
    "plan_id_ext",
    "dept_id_ext",
    "dept_name",
    "project_id_ext",
    "project_name",
    "plan_name",
    "plan_start_time",
    "plan_end_time",
    "total",
    "passed",
    "failed",
    "blocked",
    "not_run",
    "tester_ids",
    "tester_names",
}

CASE_FIELDS = {
    "plan_id_ext",
    "case_id_ext",
    "case_title",
    "priority",
    "group_path",
    "case_target",
    "preconditions",
    "steps_json",
    "expected_result",
    "keywords_json",
    "workload_minutes",
    "device_id_ext",
    "device_name",
}

RESULT_FIELDS = {
    "executed_by_id",
    "executed_by_name",
    "execution_start_time",
    "execution_end_time",
    "run_result",
    "remark",
    "failure_reason",
    "bug_ref",
    "attachments_json",
}

ALLOWED_RESULTS = {"pass", "fail", "block", "pending", "skip"}


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return str(value).strip() or None


def _normalize_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return str(value).strip() or None


def _normalize_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


def _normalize_time(value: Any, workbook) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (int, float)):
        try:
            dt = from_excel(value, workbook.epoch)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(value)
    return str(value).strip() or None


def _normalize_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if (raw.startswith("{") and raw.endswith("}")) or (
            raw.startswith("[") and raw.endswith("]")
        ):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw
        return raw
    return str(value)


def _normalize_attachments(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if (raw.startswith("{") and raw.endswith("}")) or (
            raw.startswith("[") and raw.endswith("]")
        ):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        if len(parts) > 1:
            return parts
        return raw
    return value


def _format_attachments(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        urls = []
        for item in value:
            if isinstance(item, dict):
                url = item.get("url") or item.get("file_url")
                if url:
                    urls.append(str(url))
            elif isinstance(item, str):
                urls.append(item)
        if urls:
            return ",".join(urls)
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _format_json_cell(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _template_path() -> str:
    root = current_app.root_path
    return os.path.join(root, "导入导出数据模版.xlsx")


class FeiyanService:
    @staticmethod
    def list_departments(page: int, page_size: int) -> Tuple[List[dict], int]:
        return FeiyanTestPlanRepository.list_departments(page, page_size)

    @staticmethod
    def list_test_plans(
        *,
        dept_id_ext: Optional[str],
        project_id_ext: Optional[str],
        page: int,
        page_size: int,
    ) -> Tuple[List[FeiyanTestPlan], int]:
        return FeiyanTestPlanRepository.list_plans(
            dept_id_ext=dept_id_ext,
            project_id_ext=project_id_ext,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    def list_cases(
        *,
        plan_id_ext: str,
        keyword: Optional[str],
        group_path: Optional[str],
        priority: Optional[str],
        run_result: Optional[str],
        page: int,
        page_size: int,
    ) -> Tuple[List[FeiyanPlanCaseResult], int]:
        return FeiyanPlanCaseResultRepository.list_by_plan(
            plan_id_ext=plan_id_ext,
            keyword=keyword,
            group_path=group_path,
            priority=priority,
            run_result=run_result,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    def import_excel(file_bytes: bytes, current_user=None) -> Dict[str, Any]:
        if not file_bytes:
            raise BizError("导入文件不能为空", 400)

        workbook = load_workbook(filename=BytesIO(file_bytes), data_only=True)
        sheet = workbook.active
        header_row = 2
        if sheet.max_row < header_row:
            raise BizError("Excel模板不完整", 400)

        column_fields: Dict[int, str] = {}
        for idx, cell in enumerate(sheet[header_row], start=1):
            if cell.value is None:
                continue
            header = str(cell.value).strip()
            field = HEADER_FIELD_MAP.get(header)
            if field:
                column_fields[idx] = field

        if not column_fields:
            raise BizError("Excel缺少有效字段列", 400)

        plan_cache: Dict[str, FeiyanTestPlan] = {}
        case_cache: Dict[str, FeiyanPlanCaseResult] = {}
        touched_plans: set[str] = set()

        success_count = 0
        failure_count = 0
        errors: List[Dict[str, Any]] = []

        data_start_row = 5
        for row_idx in range(data_start_row, sheet.max_row + 1):
            raw_row: Dict[str, Any] = {}
            for col_idx, field in column_fields.items():
                raw_row[field] = sheet.cell(row=row_idx, column=col_idx).value

            if all(_is_blank(value) for value in raw_row.values()):
                continue

            try:
                plan_payload = FeiyanService._build_plan_payload(raw_row, workbook)
                case_payload, result_payload = FeiyanService._build_case_payload(raw_row, workbook)
                plan_id_ext = plan_payload.get("plan_id_ext")
                case_id_ext = case_payload.get("case_id_ext")
                if not plan_id_ext:
                    raise BizError(f"第{row_idx}行缺少计划ID", 400)
                if not case_id_ext:
                    raise BizError(f"第{row_idx}行缺少用例ID", 400)

                plan = plan_cache.get(plan_id_ext)
                if plan is None:
                    plan = FeiyanTestPlanRepository.get_by_plan_id(plan_id_ext)
                    if plan is None:
                        plan = FeiyanTestPlan(
                            plan_id_ext=plan_id_ext,
                            created_by_user_id=(current_user.id if current_user else None),
                        )
                        FeiyanTestPlanRepository.add(plan)
                    plan_cache[plan_id_ext] = plan

                FeiyanService._apply_updates(plan, plan_payload, allow_blank=False)
                touched_plans.add(plan_id_ext)

                case = case_cache.get(case_id_ext)
                if case is None:
                    case = FeiyanPlanCaseResultRepository.get_by_case_id(case_id_ext)
                    if case is None:
                        case = FeiyanPlanCaseResult(
                            plan_id_ext=plan_id_ext,
                            case_id_ext=case_id_ext,
                        )
                        FeiyanPlanCaseResultRepository.add(case)
                    case_cache[case_id_ext] = case

                case.plan_id_ext = plan_id_ext
                FeiyanService._apply_updates(case, case_payload, allow_blank=False)

                if not _is_blank(result_payload.get("run_result")):
                    FeiyanService._apply_updates(case, result_payload, allow_blank=True)

                success_count += 1
            except BizError as exc:
                failure_count += 1
                errors.append({"row": row_idx, "message": exc.message})

        try:
            if touched_plans:
                for plan_id_ext in touched_plans:
                    FeiyanService.refresh_plan_statistics(plan_id_ext)

            FeiyanTestPlanRepository.commit()
            FeiyanPlanCaseResultRepository.commit()
        except Exception:
            FeiyanTestPlanRepository.rollback()
            FeiyanPlanCaseResultRepository.rollback()
            raise

        return {
            "success_count": success_count,
            "failure_count": failure_count,
            "errors": errors,
        }

    @staticmethod
    def record_result(plan_id_ext: str, payload: Dict[str, Any], current_user=None) -> FeiyanPlanCaseResult:
        plan_id_ext = _normalize_id(plan_id_ext)
        case_id_ext = _normalize_id(payload.get("case_id_ext") or payload.get("case_id"))
        if not plan_id_ext:
            raise BizError("plan_id 不能为空", 400)
        if not case_id_ext:
            raise BizError("case_id 不能为空", 400)

        case_result = FeiyanPlanCaseResultRepository.get_by_plan_and_case(plan_id_ext, case_id_ext)
        if not case_result:
            raise BizError("用例不存在", 404)

        run_result = _normalize_text(payload.get("run_result"))
        if run_result:
            run_result = run_result.lower()
        if _is_blank(run_result):
            return case_result
        if run_result not in ALLOWED_RESULTS:
            raise BizError(f"run_result 必须是 {sorted(ALLOWED_RESULTS)} 之一", 400)

        result_payload = {
            "run_result": run_result,
            "remark": _normalize_text(payload.get("remark")),
            "failure_reason": _normalize_text(payload.get("failure_reason")),
            "bug_ref": _normalize_text(payload.get("bug_ref")),
            "execution_start_time": _normalize_text(payload.get("execution_start_time")),
            "execution_end_time": _normalize_text(payload.get("execution_end_time")),
            "attachments_json": _normalize_attachments(payload.get("attachments") or payload.get("attachments_json")),
        }

        executed_by_name = _normalize_text(payload.get("executed_by_name"))
        executed_by_id = _normalize_text(payload.get("executed_by_id"))
        if _is_blank(executed_by_name) and current_user is not None:
            executed_by_name = getattr(current_user, "username", None)
        if _is_blank(executed_by_id) and current_user is not None:
            executed_by_id = str(getattr(current_user, "id", ""))

        result_payload["executed_by_name"] = executed_by_name
        result_payload["executed_by_id"] = executed_by_id

        FeiyanService._apply_updates(case_result, result_payload, allow_blank=True)
        try:
            FeiyanService.refresh_plan_statistics(plan_id_ext)
            FeiyanPlanCaseResultRepository.commit()
            FeiyanTestPlanRepository.commit()
        except Exception:
            FeiyanPlanCaseResultRepository.rollback()
            FeiyanTestPlanRepository.rollback()
            raise
        return case_result

    @staticmethod
    def export_plan(plan_id_ext: str) -> bytes:
        plan_id_ext = _normalize_id(plan_id_ext)
        if not plan_id_ext:
            raise BizError("plan_id 不能为空", 400)

        plan = FeiyanTestPlanRepository.get_by_plan_id(plan_id_ext)
        if not plan:
            raise BizError("测试计划不存在", 404)

        FeiyanService.refresh_plan_statistics(plan_id_ext)
        plan = FeiyanTestPlanRepository.get_by_plan_id(plan_id_ext)
        if not plan:
            raise BizError("测试计划不存在", 404)

        case_results, _ = FeiyanPlanCaseResultRepository.list_by_plan(
            plan_id_ext=plan_id_ext,
            page=1,
            page_size=10_000_000,
        )

        template_path = _template_path()
        if not os.path.exists(template_path):
            raise BizError("Excel模板不存在", 500)

        workbook = load_workbook(template_path)
        sheet = workbook.active

        data_start_row = 5
        if sheet.max_row >= data_start_row:
            sheet.delete_rows(data_start_row, sheet.max_row - data_start_row + 1)

        headers = []
        for cell in sheet[2]:
            header = str(cell.value).strip() if cell.value is not None else ""
            headers.append(header)

        field_by_col: Dict[int, str] = {}
        for idx, header in enumerate(headers, start=1):
            field = HEADER_FIELD_MAP.get(header)
            if field:
                field_by_col[idx] = field

        def _resolve_value(field: str, item: FeiyanPlanCaseResult) -> Any:
            if field in PLAN_FIELDS:
                return getattr(plan, field, None)
            if field == "attachments_json":
                return _format_attachments(item.attachments_json)
            if field in ("steps_json", "keywords_json"):
                return _format_json_cell(getattr(item, field, None))
            if field == "case_id_ext":
                return item.case_id_ext
            if field == "case_title":
                return item.case_title
            if hasattr(item, field):
                return getattr(item, field)
            return None

        for row_offset, item in enumerate(case_results):
            row_idx = data_start_row + row_offset
            for col_idx, field in field_by_col.items():
                value = _resolve_value(field, item)
                sheet.cell(row=row_idx, column=col_idx, value=value)

        output = BytesIO()
        workbook.save(output)
        return output.getvalue()

    @staticmethod
    def refresh_plan_statistics(plan_id_ext: str):
        plan = FeiyanTestPlanRepository.get_by_plan_id(plan_id_ext)
        if not plan:
            return

        result_stmt = db.session.query(
            func.count(FeiyanPlanCaseResult.id),
            func.sum(case((FeiyanPlanCaseResult.run_result == "pass", 1), else_=0)),
            func.sum(case((FeiyanPlanCaseResult.run_result == "fail", 1), else_=0)),
            func.sum(case((FeiyanPlanCaseResult.run_result == "block", 1), else_=0)),
            func.sum(
                case(
                    (
                        (FeiyanPlanCaseResult.run_result.is_(None))
                        | (FeiyanPlanCaseResult.run_result == "")
                        | (FeiyanPlanCaseResult.run_result == "pending")
                        | (FeiyanPlanCaseResult.run_result == "skip"),
                        1,
                    ),
                    else_=0,
                )
            ),
        ).filter(FeiyanPlanCaseResult.plan_id_ext == plan_id_ext)

        total, passed, failed, blocked, not_run = result_stmt.one()
        plan.total = int(total or 0)
        plan.passed = int(passed or 0)
        plan.failed = int(failed or 0)
        plan.blocked = int(blocked or 0)
        plan.not_run = int(not_run or 0)

    @staticmethod
    def _build_plan_payload(raw_row: Dict[str, Any], workbook) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        for field in PLAN_FIELDS:
            if field not in raw_row:
                continue
            value = raw_row.get(field)
            if field in {"plan_id_ext", "dept_id_ext", "project_id_ext"}:
                payload[field] = _normalize_id(value)
            elif field in {"total", "passed", "failed", "blocked", "not_run"}:
                payload[field] = _normalize_int(value)
            elif field in {"plan_start_time", "plan_end_time"}:
                payload[field] = _normalize_time(value, workbook)
            elif field == "tester_ids":
                payload[field] = _normalize_json_value(value)
            else:
                payload[field] = _normalize_text(value)
        return payload

    @staticmethod
    def _build_case_payload(
        raw_row: Dict[str, Any],
        workbook,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        case_payload: Dict[str, Any] = {}
        result_payload: Dict[str, Any] = {}

        for field in CASE_FIELDS:
            if field not in raw_row:
                continue
            value = raw_row.get(field)
            if field in {"plan_id_ext", "case_id_ext", "device_id_ext"}:
                case_payload[field] = _normalize_id(value)
            elif field == "workload_minutes":
                case_payload[field] = _normalize_int(value)
            elif field in {"steps_json", "keywords_json"}:
                case_payload[field] = _normalize_json_value(value)
            else:
                case_payload[field] = _normalize_text(value)

        for field in RESULT_FIELDS:
            if field not in raw_row:
                continue
            value = raw_row.get(field)
            if field == "run_result":
                normalized = _normalize_text(value)
                if normalized:
                    normalized = normalized.lower()
                result_payload[field] = normalized
            elif field in {"execution_start_time", "execution_end_time"}:
                result_payload[field] = _normalize_time(value, workbook)
            elif field == "attachments_json":
                result_payload[field] = _normalize_attachments(value)
            else:
                result_payload[field] = _normalize_text(value)

        if "run_result" in result_payload and not _is_blank(result_payload["run_result"]):
            if result_payload["run_result"] not in ALLOWED_RESULTS:
                raise BizError(f"run_result 必须是 {sorted(ALLOWED_RESULTS)} 之一", 400)

        return case_payload, result_payload

    @staticmethod
    def _apply_updates(target, payload: Dict[str, Any], *, allow_blank: bool):
        for key, value in payload.items():
            if not allow_blank and _is_blank(value):
                continue
            setattr(target, key, value)
