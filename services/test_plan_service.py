# -*- coding: utf-8 -*-
"""services/test_plan_service.py
--------------------------------------------------------------------
测试计划业务逻辑实现。
"""

from __future__ import annotations

import base64
import os
import uuid
from datetime import datetime, date
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Mapping

from flask import current_app

from constants.department_roles import DepartmentRole
from constants.test_plan import (
    DEFAULT_PLAN_STATUS,
    ExecutionResultStatus,
    TestPlanStatus,
    validate_execution_result_status,
    validate_final_execution_status,
    validate_plan_status,
)
from extensions.database import db
from models.department import DepartmentMember
from models.device_model import DeviceModel
from models.plan_case import PlanCase
from models.plan_device_model import PlanDeviceModel
from models.plan_tester import TestPlanTester
from models.project import Project
from models.test_case import TestCase
from models.test_plan import TestPlan
from models.execution import (
    ExecutionRun,
    ExecutionResult,
    ExecutionResultLog,
    EXECUTION_RESULT_ATTACHMENT_TYPE,
    EXECUTION_RESULT_LOG_ATTACHMENT_TYPE,
)
from repositories.case_group_repository import CaseGroupRepository
from repositories.device_model_repository import DeviceModelRepository
from repositories.project_repository import ProjectRepository
from repositories.test_plan_repository import TestPlanRepository
from repositories.attachment_repository import AttachmentRepository
from utils.exceptions import BizError
from utils.permissions import (
    PermissionScope,
    assert_user_in_department,
    build_permission_scope,
    get_permission_scope,
)
from utils.time_cipher import decode_encrypted_timestamp


# Maximum value for a signed INT column in MySQL. Used to clamp duration values
# derived from user-provided timestamps before persisting to the database.
MYSQL_SIGNED_INT_MAX = 2_147_483_647


class TestPlanService:
    """测试计划相关业务逻辑。"""

    @staticmethod
    def _require_scope(permission_scope: PermissionScope | None, current_user=None) -> PermissionScope:
        scope = permission_scope or get_permission_scope()
        if scope is None and current_user is not None:
            scope = build_permission_scope(current_user)
        if scope is None:
            raise BizError("权限校验失败（缺少权限范围）", 500)
        return scope

    @staticmethod
    def _ensure_plan_access(
        plan: TestPlan,
        scope: PermissionScope,
        current_user,
        min_role: DepartmentRole | None = None,
    ):
        department_id = plan.project.department_id if plan.project else None
        assert_user_in_department(department_id, user=current_user, scope=scope)
        if min_role and not scope.has_department_role(department_id, min_role):
            raise BizError("无权限操作该测试计划", 403)

    @staticmethod
    def create(
        *,
        current_user,
        project_id: int,
        name: str,
        description: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str | date] = None,
        end_date: Optional[str | date] = None,
        case_ids: Optional[Sequence[int]] = None,
        case_group_ids: Optional[Sequence[int]] = None,
        single_execution_case_ids: Optional[Sequence[int]] = None,
        device_model_ids: Optional[Sequence[int]] = None,
        tester_user_ids: Optional[Sequence[int]] = None,
        permission_scope: PermissionScope | None = None,
    ) -> TestPlan:
        scope = TestPlanService._require_scope(permission_scope, current_user)
        if not name or not name.strip():
            raise BizError("测试计划名称不能为空", 400)

        project = TestPlanService._get_project(project_id)
        if current_user:
            assert_user_in_department(project.department_id, user=current_user, scope=scope)
        if not scope.has_department_role(project.department_id, DepartmentRole.PROJECT_ADMIN):
            raise BizError("需要项目管理员或以上权限", 403)

        status_value = status or DEFAULT_PLAN_STATUS
        validate_plan_status(status_value)

        start_dt = TestPlanService._parse_date(start_date, "start_date")
        end_dt = TestPlanService._parse_date(end_date, "end_date")
        if start_dt and end_dt and start_dt > end_dt:
            raise BizError("开始日期不能晚于结束日期", 400)

        collected_case_ids = set(case_ids or [])
        if case_group_ids:
            group_case_ids = CaseGroupRepository.collect_test_case_ids_by_group_ids(list(case_group_ids))
            collected_case_ids.update(group_case_ids)
        if not collected_case_ids:
            raise BizError("测试计划至少需要包含一个用例", 400)

        single_exec_ids = set(single_execution_case_ids or [])
        invalid_single_exec = single_exec_ids - collected_case_ids
        if invalid_single_exec:
            raise BizError("单次执行用例必须包含在计划用例列表中", 400)

        test_cases = TestPlanService._load_test_cases(collected_case_ids, project)
        devices = TestPlanService._load_device_models(device_model_ids or [], project)
        tester_ids = TestPlanService._validate_testers(tester_user_ids or [], project)

        plan = TestPlanRepository.create(
            project_id=project.id,
            name=name.strip(),
            status=status_value,
            description=description,
            created_by=current_user.id if current_user else None,
            start_date=start_dt,
            end_date=end_dt,
        )

        device_model_map: Dict[int, PlanDeviceModel] = {}
        for device in devices:
            plan_device = PlanDeviceModel(
                plan_id=plan.id,
                device_model_id=device.id,
                snapshot_name=device.name,
                snapshot_model_code=device.model_code,
                snapshot_category=device.category,
            )
            plan.plan_device_models.append(plan_device)
            TestPlanRepository.add_plan_device_model(plan_device)
            device_model_map[device.id] = plan_device

        # 创建计划用例快照
        ordered_cases = sorted(test_cases, key=lambda c: c.id)
        for order_no, case in enumerate(ordered_cases, start=1):
            group_path = case.group.path if case.group else None
            require_all_devices = bool(device_model_map) and case.id not in single_exec_ids
            plan_case = PlanCase(
                plan_id=plan.id,
                case_id=case.id,
                snapshot_title=case.title,
                snapshot_steps=case.steps,
                snapshot_expected_result=case.expected_result,
                snapshot_preconditions=case.preconditions,
                snapshot_priority=case.priority,
                snapshot_workload_minutes=case.workload_minutes,
                include=True,
                order_no=order_no,
                group_path_cache=group_path,
                require_all_devices=require_all_devices,
            )
            plan.plan_cases.append(plan_case)
            TestPlanRepository.add_plan_case(plan_case)

        # 分配测试人员
        for uid in tester_ids:
            plan_tester = TestPlanTester(plan_id=plan.id, user_id=uid)
            plan.plan_testers.append(plan_tester)
            TestPlanRepository.add_plan_tester(plan_tester)

        # 初始化执行批次与结果
        run = ExecutionRun(
            plan_id=plan.id,
            name="默认执行",
            run_type="manual",
            status="running",
            triggered_by=current_user.id if current_user else None,
            start_time=datetime.utcnow(),
        )
        TestPlanRepository.add_execution_run(run)
        db.session.flush()

        total_results = 0
        for plan_case in plan.plan_cases:
            if plan_case.require_all_devices and device_model_map:
                for device_id, plan_device in device_model_map.items():
                    result = ExecutionResult(
                        run_id=run.id,
                        plan_case_id=plan_case.id,
                        device_model_id=device_id,
                        plan_device_model_id=plan_device.id,
                        result=ExecutionResultStatus.PENDING.value,
                    )
                    TestPlanRepository.add_execution_result(result)
                    total_results += 1
            else:
                result = ExecutionResult(
                    run_id=run.id,
                    plan_case_id=plan_case.id,
                    device_model_id=None,
                    plan_device_model_id=None,
                    result=ExecutionResultStatus.PENDING.value,
                )
                TestPlanRepository.add_execution_result(result)
                total_results += 1

        run.total = total_results
        run.not_run = total_results
        run.executed = 0
        run.passed = 0
        run.failed = 0
        run.blocked = 0
        run.skipped = 0

        TestPlanRepository.commit()
        return TestPlanRepository.get_by_id(plan.id)

    @staticmethod
    def get(
        plan_id: int,
        *,
        current_user=None,
        permission_scope: PermissionScope | None = None,
    ) -> TestPlan:
        scope = TestPlanService._require_scope(permission_scope, current_user)
        plan = TestPlanRepository.get_by_id(plan_id)
        if not plan:
            raise BizError("测试计划不存在", 404)
        TestPlanService._ensure_plan_access(plan, scope, current_user)
        return plan

    @staticmethod
    def get_summary(
        plan_id: int,
        *,
        current_user=None,
        permission_scope: PermissionScope | None = None,
    ) -> TestPlan:
        scope = TestPlanService._require_scope(permission_scope, current_user)
        plan = TestPlanRepository.get_by_id(
            plan_id,
            load_project=True,
            load_creator=True,
            load_cases=False,
            load_case_results=False,
            load_case_result_logs=False,
            load_case_result_log_attachments=False,
            load_case_result_attachments=False,
            load_device_models=True,
            load_testers=True,
            load_execution_runs=True,
            load_execution_run_results=False,
        )
        if not plan:
            raise BizError("测试计划不存在", 404)
        TestPlanService._ensure_plan_access(plan, scope, current_user)
        return plan

    @staticmethod
    def list_plan_cases(
        plan_id: int,
        *,
        group_paths: Optional[Sequence[str]] = None,
        title_keyword: Optional[str] = None,
        priorities: Optional[Sequence[str]] = None,
        statuses: Optional[Sequence[str]] = None,
        device_model_id: Optional[int] = None,
        current_user=None,
        permission_scope: PermissionScope | None = None,
    ) -> List[PlanCase]:
        scope = TestPlanService._require_scope(permission_scope, current_user)
        plan = TestPlanRepository.get_by_id(
            plan_id,
            load_project=True,
            load_creator=False,
            load_cases=True,
            load_case_results=True,
            load_case_result_logs=False,
            load_case_result_log_attachments=False,
            load_case_result_attachments=False,
            load_device_models=False,
            load_testers=False,
            load_execution_runs=False,
            load_execution_run_results=False,
        )
        if not plan:
            raise BizError("测试计划不存在", 404)
        TestPlanService._ensure_plan_access(plan, scope, current_user)

        cases = list(plan.plan_cases)

        normalized_groups: list[str] = []
        include_ungrouped = False
        if group_paths:
            for raw in group_paths:
                if raw is None:
                    continue
                value = raw.strip()
                if not value or value.lower() in {"__ungrouped__", "ungrouped", "__none__"}:
                    include_ungrouped = True
                    continue
                normalized_groups.append(value.rstrip("/"))
        group_filter_enabled = bool(normalized_groups or include_ungrouped)

        title_filter = title_keyword.strip().lower() if title_keyword else None

        priority_set = {
            priority.strip().lower()
            for priority in priorities or []
            if priority and priority.strip()
        }

        status_set: set[str] = set()
        for status in statuses or []:
            if not status:
                continue
            value = status.strip().lower()
            validate_execution_result_status(value)
            status_set.add(value)

        filtered: list[PlanCase] = []
        for plan_case in cases:
            if group_filter_enabled:
                case_group = (plan_case.group_path_cache or "").rstrip("/")
                matched = False
                if case_group:
                    for group_path in normalized_groups:
                        if (
                            case_group == group_path
                            or case_group.startswith(f"{group_path}/")
                        ):
                            matched = True
                            break
                else:
                    matched = include_ungrouped
                if not matched:
                    continue

            if title_filter:
                case_title = plan_case.snapshot_title or ""
                if title_filter not in case_title.lower():
                    continue

            if priority_set:
                case_priority = (plan_case.snapshot_priority or "").lower()
                if case_priority not in priority_set:
                    continue

            if status_set:
                latest_status = TestPlanService._get_plan_case_latest_status(plan_case)
                if latest_status not in status_set:
                    continue

            filtered.append(plan_case)

        if device_model_id is not None:
            filtered = [
                plan_case
                for plan_case in filtered
                if (not plan_case.require_all_devices)
                or any(
                    result.device_model_id == device_model_id
                    for result in plan_case.execution_results
                )
            ]

        return filtered

    @staticmethod
    def get_plan_case(
        plan_id: int,
        plan_case_id: int,
        *,
        current_user=None,
        permission_scope: PermissionScope | None = None,
    ) -> PlanCase:
        scope = TestPlanService._require_scope(permission_scope, current_user)
        plan = TestPlanRepository.get_by_id(
            plan_id,
            load_project=True,
            load_creator=False,
            load_cases=False,
            load_case_results=False,
            load_case_result_logs=False,
            load_case_result_log_attachments=False,
            load_case_result_attachments=False,
            load_device_models=False,
            load_testers=False,
            load_execution_runs=False,
            load_execution_run_results=False,
        )
        if not plan:
            raise BizError("测试计划不存在", 404)
        TestPlanService._ensure_plan_access(plan, scope, current_user)

        plan_case = TestPlanRepository.get_plan_case(
            plan_id,
            plan_case_id,
            include_results=True,
            include_result_logs=True,
            include_result_log_attachments=True,
            include_result_attachments=True,
        )
        if not plan_case:
            raise BizError("计划用例不存在", 404)
        return plan_case

    @staticmethod
    def _get_plan_case_latest_status(plan_case: PlanCase) -> str:
        latest = ExecutionResultStatus.PENDING.value
        latest_at = None
        for result in plan_case.execution_results:
            result_value = result.result or ExecutionResultStatus.PENDING.value
            if result_value == ExecutionResultStatus.PENDING.value:
                continue
            timestamp = result.executed_at or result.updated_at
            if not latest_at or (timestamp and timestamp > latest_at):
                latest = result_value
                latest_at = timestamp
        return latest

    @staticmethod
    def list(
        *,
        project_id: Optional[int] = None,
        department_id: Optional[int] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        order_desc: bool = True,
        permission_scope: PermissionScope | None = None,
    ) -> Tuple[List[TestPlan], int]:
        scope = TestPlanService._require_scope(permission_scope)
        if status:
            validate_plan_status(status)
        accessible_ids = scope.accessible_department_ids()
        if department_id:
            if not scope.has_department_role(department_id):
                raise BizError("无权访问该部门的测试计划", 403)
            if accessible_ids is None:
                accessible_ids = [department_id]
            else:
                if department_id not in accessible_ids:
                    return [], 0
                accessible_ids = [department_id]
        return TestPlanRepository.list(
            project_id=project_id,
            department_id=department_id,
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
            order_desc=order_desc,
            accessible_department_ids=accessible_ids,
        )

    @staticmethod
    def update(
        plan_id: int,
        *,
        current_user,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str | date] = None,
        end_date: Optional[str | date] = None,
        tester_user_ids: Optional[Sequence[int]] = None,
        permission_scope: PermissionScope | None = None,
    ) -> TestPlan:
        scope = TestPlanService._require_scope(permission_scope, current_user)
        plan = TestPlanService.get(
            plan_id,
            current_user=current_user,
            permission_scope=scope,
        )
        if plan.is_archived:
            raise BizError("测试计划已归档，禁止修改", 400)

        project = plan.project
        if current_user:
            assert_user_in_department(project.department_id, user=current_user, scope=scope)
        TestPlanService._ensure_plan_access(plan, scope, current_user, DepartmentRole.PROJECT_ADMIN)

        if name is not None:
            if not name.strip():
                raise BizError("测试计划名称不能为空", 400)
            plan.name = name.strip()
        if description is not None:
            plan.description = description

        if start_date is not None:
            plan.start_date = TestPlanService._parse_date(start_date, "start_date")
        if end_date is not None:
            plan.end_date = TestPlanService._parse_date(end_date, "end_date")
        if plan.start_date and plan.end_date and plan.start_date > plan.end_date:
            raise BizError("开始日期不能晚于结束日期", 400)

        if status is not None:
            validate_plan_status(status)
            plan.status = status

        if tester_user_ids is not None:
            new_tester_ids = TestPlanService._validate_testers(tester_user_ids, project)
            new_tester_id_set = set(new_tester_ids)
            existing_testers = {tester.user_id: tester for tester in plan.plan_testers}

            # 删除未包含的执行人
            for tester in list(plan.plan_testers):
                if tester.user_id not in new_tester_id_set:
                    plan.plan_testers.remove(tester)
                    db.session.delete(tester)

            # 新增执行人
            for user_id in new_tester_ids:
                if user_id not in existing_testers:
                    plan_tester = TestPlanTester(plan_id=plan.id, user_id=user_id)
                    plan.plan_testers.append(plan_tester)
                    TestPlanRepository.add_plan_tester(plan_tester)

        TestPlanRepository.commit()
        return TestPlanRepository.get_by_id(plan.id)

    @staticmethod
    def delete(
        plan_id: int,
        *,
        current_user,
        permission_scope: PermissionScope | None = None,
    ):
        scope = TestPlanService._require_scope(permission_scope, current_user)
        plan = TestPlanService.get(
            plan_id,
            current_user=current_user,
            permission_scope=scope,
        )
        if plan.is_archived:
            raise BizError("归档状态的测试计划不可删除", 400)
        project = plan.project
        if current_user:
            assert_user_in_department(project.department_id, user=current_user, scope=scope)
        TestPlanService._ensure_plan_access(plan, scope, current_user, DepartmentRole.PROJECT_ADMIN)
        TestPlanRepository.delete(plan)
        TestPlanRepository.commit()

    @staticmethod
    def record_result(
        plan_id: int,
        *,
        current_user,
        plan_case_id: int,
        result: str,
        device_model_id: Optional[int] = None,
        remark: Optional[str] = None,
        failure_reason: Optional[str] = None,
        bug_ref: Optional[str] = None,
        execution_start_time: Optional[str] = None,
        execution_end_time: Optional[str] = None,
        attachments: Optional[Sequence[Mapping]] = None,
        permission_scope: PermissionScope | None = None,
    ) -> ExecutionResult:
        scope = TestPlanService._require_scope(permission_scope, current_user)
        plan = TestPlanRepository.get_by_id(
            plan_id,
            load_project=True,
            load_creator=False,
            load_cases=False,
            load_case_results=False,
            load_case_result_logs=False,
            load_case_result_log_attachments=False,
            load_case_result_attachments=False,
            load_device_models=False,
            load_testers=True,
            load_execution_runs=True,
            load_execution_run_results=False,
        )
        if not plan:
            raise BizError("测试计划不存在", 404)
        TestPlanService._ensure_plan_access(plan, scope, current_user)
        if plan.is_archived:
            raise BizError("测试计划已归档，禁止修改", 400)

        if not TestPlanService._user_can_execute(plan, current_user, scope):
            raise BizError("无权限执行该测试计划", 403)

        plan_case = TestPlanRepository.get_plan_case(
            plan_id,
            plan_case_id,
            include_results=False,
            include_result_logs=False,
            include_result_log_attachments=False,
            include_result_attachments=False,
        )
        if not plan_case:
            raise BizError("计划用例不存在", 404)

        validate_final_execution_status(result)

        query = ExecutionResult.query.join(
            ExecutionRun, ExecutionResult.run_id == ExecutionRun.id
        ).filter(
            ExecutionRun.plan_id == plan.id,
            ExecutionResult.plan_case_id == plan_case.id,
        )

        if plan_case.require_all_devices:
            if device_model_id is None:
                raise BizError("该用例需要指定机型执行", 400)
            query = query.filter(ExecutionResult.device_model_id == device_model_id)
        else:
            if device_model_id is not None:
                query = query.filter(ExecutionResult.device_model_id == device_model_id)
            else:
                query = query.filter(ExecutionResult.device_model_id.is_(None))

        execution_result = query.first()
        if not execution_result:
            raise BizError("执行记录不存在", 404)

        def _normalize_time_token(raw_value: Optional[str]) -> Optional[str]:
            if raw_value is None:
                return None
            if isinstance(raw_value, str):
                token = raw_value.strip()
            else:
                token = str(raw_value).strip()
            return token or None

        normalized_start_token = _normalize_time_token(execution_start_time)
        normalized_end_token = _normalize_time_token(execution_end_time)

        if not normalized_start_token or not normalized_end_token:
            raise BizError("执行开始时间和结束时间不能为空", 400)

        start_dt = decode_encrypted_timestamp(normalized_start_token)
        end_dt = decode_encrypted_timestamp(normalized_end_token)
        if start_dt and end_dt and end_dt < start_dt:
            raise BizError("结束时间不能早于开始时间", 400)

        duration_ms_value = None
        if start_dt and end_dt:
            duration_ms_value = int((end_dt - start_dt).total_seconds() * 1000)
            if duration_ms_value > MYSQL_SIGNED_INT_MAX:
                duration_ms_value = MYSQL_SIGNED_INT_MAX
            elif duration_ms_value < 0:
                duration_ms_value = 0

        execution_result.result = result
        execution_result.executed_by = current_user.id if current_user else None
        execution_result.executed_at = datetime.utcnow()
        execution_result.remark = remark
        execution_result.failure_reason = failure_reason
        execution_result.bug_ref = bug_ref
        execution_result.execution_start_time = start_dt
        execution_result.execution_end_time = end_dt
        execution_result.duration_ms = duration_ms_value

        log = ExecutionResultLog(
            execution_result_id=execution_result.id,
            run_id=execution_result.run_id,
            plan_case_id=execution_result.plan_case_id,
            device_model_id=execution_result.device_model_id,
            result=execution_result.result,
            executed_by=execution_result.executed_by,
            executed_at=execution_result.executed_at,
            execution_start_time=start_dt,
            execution_end_time=end_dt,
            duration_ms=duration_ms_value,
            failure_reason=failure_reason,
            bug_ref=bug_ref,
            remark=remark,
        )
        TestPlanRepository.add_execution_result_log(log)
        db.session.flush()

        attachment_payloads = list(attachments or [])
        if attachment_payloads:
            attachment_payloads = [
                TestPlanService._prepare_attachment_payload(
                    payload,
                    storage_dir=current_app.config.get("ATTACHMENT_STORAGE_DIR"),
                    business_id=execution_result.id,
                    uploaded_by=current_user.id if current_user else None,
                )
                for payload in attachment_payloads
            ]
        for payload in attachment_payloads:
            TestPlanService._validate_attachment_payload(payload)
        AttachmentRepository.replace_target_attachments(
            EXECUTION_RESULT_ATTACHMENT_TYPE,
            execution_result.id,
            attachment_payloads,
        )
        if attachment_payloads:
            for payload in attachment_payloads:
                AttachmentRepository.add_attachment(
                    EXECUTION_RESULT_LOG_ATTACHMENT_TYPE,
                    log.id,
                    payload,
                )

        TestPlanService._refresh_statistics(plan)
        TestPlanRepository.commit()
        return execution_result

    @staticmethod
    def _validate_attachment_payload(payload: Mapping):
        required_fields = ["file_name", "stored_file_name", "file_path"]
        for field in required_fields:
            value = payload.get(field)
            if not value:
                raise BizError(f"附件字段 {field} 不能为空", 400)

    @staticmethod
    def _prepare_attachment_payload(
        payload: Mapping,
        *,
        storage_dir: Optional[str],
        business_id: int,
        uploaded_by: Optional[int],
    ) -> Mapping:
        """将附件负载补充为本地存储所需的信息并完成落盘。"""

        stored_file_name = payload.get("stored_file_name")
        file_path = payload.get("file_path")
        file_name = payload.get("file_name")

        if not file_name:
            raise BizError("附件缺少文件名", 400)

        safe_file_name = os.path.basename(file_name)

        if stored_file_name and file_path:
            result_payload = dict(payload)
            result_payload["file_name"] = safe_file_name
            if uploaded_by is not None and result_payload.get("uploaded_by") is None:
                result_payload["uploaded_by"] = uploaded_by
            return result_payload

        if not storage_dir:
            raise BizError("附件存储目录未配置", 500)

        file_content = payload.get("content") or payload.get("file_content")
        if not file_content:
            raise BizError("附件缺少内容", 400)

        if "," in file_content:
            file_content = file_content.split(",", 1)[1]

        try:
            file_bytes = base64.b64decode(file_content)
        except Exception as exc:  # noqa: BLE001
            raise BizError("附件内容解码失败", 400) from exc

        storage_root = os.path.abspath(storage_dir)
        date_dir = datetime.utcnow().strftime("%Y%m%d")
        business_dir = os.path.join(storage_root, date_dir, str(business_id))
        os.makedirs(business_dir, exist_ok=True)

        file_ext = os.path.splitext(safe_file_name)[1]
        generated_name = f"{uuid.uuid4().hex}{file_ext}"
        stored_file_name = generated_name
        relative_path = os.path.join(date_dir, str(business_id), stored_file_name)
        absolute_path = os.path.join(storage_root, relative_path)

        with open(absolute_path, "wb") as fp:
            fp.write(file_bytes)

        result_payload = dict(payload)
        result_payload["file_name"] = safe_file_name
        result_payload["stored_file_name"] = stored_file_name
        result_payload["file_path"] = relative_path.replace(os.sep, "/")
        result_payload.pop("content", None)
        result_payload.pop("file_content", None)
        result_payload["size"] = result_payload.get("size") or len(file_bytes)
        if uploaded_by is not None:
            result_payload["uploaded_by"] = uploaded_by

        return result_payload

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_date(value: Optional[str | date], field_name: str) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                raise BizError(f"{field_name} 格式必须为 YYYY-MM-DD", 400)
        raise BizError(f"{field_name} 格式不正确", 400)

    @staticmethod
    def _get_project(project_id: int) -> Project:
        project = ProjectRepository.get_by_id(project_id)
        if not project:
            raise BizError("项目不存在", 404)
        return project

    @staticmethod
    def _load_test_cases(case_ids: Iterable[int], project: Project) -> List[TestCase]:
        if not case_ids:
            return []
        items = (
            TestCase.query
            .filter(
                TestCase.id.in_(case_ids),
                TestCase.is_deleted == False,  # noqa: E712
            )
            .all()
        )
        found_ids = {item.id for item in items}
        missing = set(case_ids) - found_ids
        if missing:
            raise BizError(f"部分用例不存在或已删除: {sorted(missing)}", 404)
        for item in items:
            if item.department_id != project.department_id:
                raise BizError("测试用例必须属于项目所在部门", 400)
        return items

    @staticmethod
    def _load_device_models(device_model_ids: Iterable[int], project: Project) -> List[DeviceModel]:
        devices = []
        for device_id in device_model_ids:
            device = DeviceModelRepository.get_by_id(device_id, include_inactive=True)
            if not device:
                raise BizError(f"机型 {device_id} 不存在", 404)
            if device.department_id != project.department_id:
                raise BizError("机型必须属于项目所在部门", 400)
            devices.append(device)
        return devices

    @staticmethod
    def _validate_testers(user_ids: Iterable[int], project: Project) -> List[int]:
        unique_ids = list(dict.fromkeys(user_ids))
        if not unique_ids:
            raise BizError("测试计划必须指定至少一名执行人员", 400)

        memberships = (
            DepartmentMember.query
            .filter(
                DepartmentMember.department_id == project.department_id,
                DepartmentMember.user_id.in_(unique_ids),
            )
            .all()
        )
        found_user_ids = {m.user_id for m in memberships}
        missing = set(unique_ids) - found_user_ids
        if missing:
            raise BizError(f"以下用户不属于项目部门，无法指派: {sorted(missing)}", 400)
        return unique_ids

    @staticmethod
    def _user_can_execute(
        plan: TestPlan,
        user,
        permission_scope: PermissionScope | None = None,
    ) -> bool:
        scope = permission_scope or get_permission_scope()
        department_id = plan.project.department_id if plan.project else None
        if scope and department_id is not None:
            if scope.is_system_admin():
                return True
            if scope.has_department_role(department_id, DepartmentRole.PROJECT_ADMIN):
                return True
        if not user:
            return False
        assigned_ids = {tester.user_id for tester in plan.plan_testers}
        return user.id in assigned_ids

    @staticmethod
    def _refresh_statistics(plan: TestPlan):
        for run in plan.execution_runs:
            results = ExecutionResult.query.filter(ExecutionResult.run_id == run.id).all()
            run.total = len(results)
            run.passed = sum(1 for r in results if r.result == ExecutionResultStatus.PASS.value)
            run.failed = sum(1 for r in results if r.result == ExecutionResultStatus.FAIL.value)
            run.blocked = sum(1 for r in results if r.result == ExecutionResultStatus.BLOCK.value)
            run.skipped = sum(1 for r in results if r.result == ExecutionResultStatus.SKIP.value)
            run.executed = run.passed + run.failed + run.blocked + run.skipped
            run.not_run = run.total - run.executed
            if run.not_run == 0:
                run.status = "finished"
                run.end_time = run.end_time or datetime.utcnow()
            else:
                run.status = "running"
                run.end_time = None

        if plan.status != TestPlanStatus.ARCHIVED.value:
            unfinished = any(run.not_run for run in plan.execution_runs)
            if not unfinished:
                plan.status = TestPlanStatus.COMPLETED.value
