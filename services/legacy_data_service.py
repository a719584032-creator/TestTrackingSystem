"""Business logic for accessing legacy test management data."""
from __future__ import annotations

import os
from functools import wraps
from typing import Dict, List, Optional, Sequence

from flask import current_app

from repositories.legacy_data_repository import LegacyDataRepository
from utils.exceptions import BizError


def _ensure_legacy_configured(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RuntimeError as exc:
            raise BizError(message="旧数据数据库未配置", code=500) from exc
    return wrapper


class LegacyDataService:
    """Service layer orchestrating legacy repository calls."""

    @staticmethod
    @_ensure_legacy_configured
    def list_projects(keyword: Optional[str] = None) -> List[str]:  # type: ignore[misc]
        return LegacyDataRepository.list_projects(keyword)

    @staticmethod
    @_ensure_legacy_configured
    def list_plans(project_name: str, keyword: Optional[str] = None) -> List[Dict]:  # type: ignore[misc]
        return LegacyDataRepository.list_plans(project_name, keyword)

    @staticmethod
    @_ensure_legacy_configured
    def list_models(plan_id: int) -> List[Dict]:  # type: ignore[misc]
        return LegacyDataRepository.list_models(plan_id)

    @staticmethod
    @_ensure_legacy_configured
    def get_plan_statistics(plan_id: int) -> Dict:  # type: ignore[misc]
        case_time = LegacyDataRepository.count_case_time(plan_id)
        workloading = LegacyDataRepository.count_workloading(plan_id)
        case_count = LegacyDataRepository.count_case(plan_id)
        executed_cases = LegacyDataRepository.count_executed_case(plan_id)
        result_counts = LegacyDataRepository.count_test_case_results(plan_id)
        testers = LegacyDataRepository.list_testers(plan_id)

        def _percent(part: int, whole: int) -> str:
            if whole <= 0:
                return "0.00%"
            return f"{(part / whole) * 100:.2f}%"

        return {
            "case_count": case_count,
            "executed_cases_count": executed_cases,
            "execution_progress": _percent(executed_cases, case_count),
            "pass_rate": _percent(result_counts.get("pass_count", 0), case_count),
            "fail_rate": _percent(result_counts.get("fail_count", 0), case_count),
            "block_rate": _percent(result_counts.get("block_count", 0), case_count),
            "pass_count": result_counts.get("pass_count", 0),
            "fail_count": result_counts.get("fail_count", 0),
            "block_count": result_counts.get("block_count", 0),
            "case_time_count": case_time,
            "workloading_time": workloading,
            "tester": testers,
        }

    @staticmethod
    @_ensure_legacy_configured
    def list_sheets(plan_id: int) -> List[Dict]:  # type: ignore[misc]
        return LegacyDataRepository.list_sheets(plan_id)

    @staticmethod
    @_ensure_legacy_configured
    def list_case_status(model_id: int, sheet_id: int) -> List[Dict]:  # type: ignore[misc]
        return LegacyDataRepository.list_case_status(model_id, sheet_id)

    @staticmethod
    @_ensure_legacy_configured
    def list_images(execution_ids: Sequence[int], host_url: str) -> Dict[str, List[Dict]]:  # type: ignore[misc]
        rows = LegacyDataRepository.list_images(execution_ids)
        if not rows:
            return {}

        image_root = current_app.config.get("LEGACY_IMAGE_ROOT")
        response: Dict[str, List[Dict]] = {}
        for row in rows:
            normalized = {key.lower(): value for key, value in row.items()}
            execution_id = str(normalized.get("executionid"))
            if not execution_id:
                continue
            file_path = normalized.get("filepath")
            stored_file_name = normalized.get("storedfilename") or normalized.get("storefilename")
            original_file_name = normalized.get("originalfilename") or normalized.get("filename")
            file_size = normalized.get("filesize")
            mime_type = normalized.get("mimetype")
            upload_time = normalized.get("time") or normalized.get("uploadtime")

            # relative_path = None
            # if isinstance(file_path, str) and file_path:
            #     path_to_use = file_path
            #     if image_root and os.path.exists(path_to_use):
            #         try:
            #             relative_path = os.path.relpath(path_to_use, image_root)
            #         except ValueError:
            #             relative_path = os.path.basename(path_to_use)
            #     else:
            #         relative_path = os.path.basename(path_to_use)
            #
            # url = None
            # if relative_path:
            #     sanitized = relative_path.replace(os.sep, "/")
            #     url = f"{host_url.rstrip('/')}/uploads/{sanitized}" if host_url else None

            if file_path.startswith("/data"):
                cleaned_path = file_path[len("/data"):]
            else:
                cleaned_path = file_path

            image_info = {
                "execution_id": int(execution_id) if execution_id.isdigit() else execution_id,
                "original_file_name": original_file_name,
                "stored_file_name": stored_file_name,
                "file_path": file_path,
                "file_size": file_size,
                "mime_type": mime_type,
                "time": upload_time.strftime("%Y-%m-%d %H:%M:%S") if hasattr(upload_time, "strftime") else upload_time,
                "url": f"{host_url.rstrip('/')}{cleaned_path}" if host_url else None,
            }
            response.setdefault(execution_id, []).append(image_info)
        return response
