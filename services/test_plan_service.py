# -*- coding: utf-8 -*-
"""services/test_plan_service.py
--------------------------------------------------------------------
测试计划业务逻辑实现。
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, date
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Mapping

from flask import current_app

from constants.roles import Role
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
from utils.permissions import assert_user_in_department
from utils.time_cipher import decode_encrypted_timestamp_optional
from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.orm import selectinload


class TestPlanService:
    """测试计划相关业务逻辑。"""

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
    ) -> TestPlan:
        if not name or not name.strip():
            raise BizError("测试计划名称不能为空", 400)

        project = TestPlanService._get_project(project_id)
        if current_user:
            assert_user_in_department(project.department_id, user=current_user)

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
        load_details: bool = True,
        **options,
    ) -> TestPlan:
        plan = TestPlanRepository.get_by_id(plan_id, load_details=load_details, **options)
        if not plan:
            raise BizError("测试计划不存在", 404)
        return plan

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
    ) -> Tuple[List[TestPlan], int]:
        if status:
            validate_plan_status(status)
        return TestPlanRepository.list(
            project_id=project_id,
            department_id=department_id,
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
            order_desc=order_desc,
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
    ) -> TestPlan:
        plan = TestPlanService.get(plan_id)
        if plan.is_archived:
            raise BizError("测试计划已归档，禁止修改", 400)

        project = plan.project
        if current_user:
            assert_user_in_department(project.department_id, user=current_user)

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
    def delete(plan_id: int, *, current_user):
        plan = TestPlanService.get(plan_id)
        if plan.is_archived:
            raise BizError("归档状态的测试计划不可删除", 400)
        project = plan.project
        if current_user:
            assert_user_in_department(project.department_id, user=current_user)
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
    ) -> ExecutionResult:
        plan = TestPlanService.get(plan_id)
        if plan.is_archived:
            raise BizError("测试计划已归档，禁止修改", 400)

        if not TestPlanService._user_can_execute(plan, current_user):
            raise BizError("无权限执行该测试计划", 403)

        plan_case = next((case for case in plan.plan_cases if case.id == plan_case_id), None)
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

        start_dt = decode_encrypted_timestamp_optional(execution_start_time)
        end_dt = decode_encrypted_timestamp_optional(execution_end_time)
        if (start_dt and not end_dt) or (end_dt and not start_dt):
            raise BizError("开始时间和结束时间必须同时提供", 400)
        if start_dt and end_dt and end_dt < start_dt:
            raise BizError("结束时间不能早于开始时间", 400)

        duration_ms_value = None
        if start_dt and end_dt:
            duration_ms_value = int((end_dt - start_dt).total_seconds() * 1000)

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

    # ------------------------------------------------------------------
    # 计划信息拆分查询
    # ------------------------------------------------------------------
    @staticmethod
    def get_overview(plan_id: int, includes: Optional[Iterable[str]] = None) -> Dict:
        include_set = TestPlanService._normalize_includes(includes)
        include_stats = "stats" in include_set
        include_testers = "testers" in include_set
        include_device_models = "device_models" in include_set
        include_runs = include_stats or "execution_runs" in include_set

        plan = TestPlanService.get(
            plan_id,
            load_details=False,
            load_device_models=include_device_models,
            load_testers=include_testers,
            load_runs=include_runs,
            load_run_results=False,
        )

        project_payload = None
        if plan.project:
            project_payload = {
                "id": plan.project.id,
                "name": plan.project.name,
            }

        data = {
            "id": plan.id,
            "name": plan.name,
            "status": plan.status,
            "description": plan.description,
            "start_date": plan.start_date.isoformat() if plan.start_date else None,
            "end_date": plan.end_date.isoformat() if plan.end_date else None,
            "project": project_payload,
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        }

        if include_testers:
            data["testers"] = [
                TestPlanService._serialize_tester_summary(tester)
                for tester in plan.plan_testers
            ]

        if include_device_models:
            data["device_models"] = [
                TestPlanService._serialize_device_summary(device)
                for device in plan.plan_device_models
            ]

        if include_runs:
            ordered_runs = sorted(
                plan.execution_runs,
                key=lambda run: ((run.created_at or datetime.min), run.id or 0),
                reverse=True,
            )
            data["execution_runs"] = [
                TestPlanService._serialize_run_summary(run) for run in ordered_runs
            ]

        if include_stats:
            latest_run = TestPlanService._select_latest_run(plan.execution_runs)
            data["statistics"] = TestPlanService._build_statistics_from_run(latest_run)

        return data

    @staticmethod
    def list_plan_cases(
        plan_id: int,
        *,
        statuses: Optional[Iterable[str]] = None,
        priorities: Optional[Iterable[str]] = None,
        include_value: Optional[bool] = None,
        require_all_devices: Optional[bool] = None,
        device_model_id: Optional[int] = None,
        keyword: Optional[str] = None,
        order_by: str = "order_no",
        cursor: Optional[str] = None,
        page_size: int = 50,
    ) -> Dict:
        TestPlanService.get(
            plan_id,
            load_details=False,
            load_cases=False,
            load_device_models=False,
            load_testers=False,
            load_runs=False,
        )

        page_size = max(1, min(page_size, 200))

        counts_subquery = TestPlanService._build_case_result_summary_subquery(plan_id)
        aggregated_status_expr = func.coalesce(
            case(
                (counts_subquery.c.fail_count > 0, ExecutionResultStatus.FAIL.value),
                (counts_subquery.c.block_count > 0, ExecutionResultStatus.BLOCK.value),
                (counts_subquery.c.skip_count > 0, ExecutionResultStatus.SKIP.value),
                (counts_subquery.c.pending_count > 0, ExecutionResultStatus.PENDING.value),
                else_=ExecutionResultStatus.PASS.value,
            ),
            ExecutionResultStatus.PENDING.value,
        )

        aggregated_status_column = aggregated_status_expr.label("aggregated_status")

        stmt = (
            select(
                PlanCase,
                aggregated_status_column,
                counts_subquery.c.total_results,
                counts_subquery.c.executed_results,
                counts_subquery.c.pending_count,
                counts_subquery.c.pass_count,
                counts_subquery.c.fail_count,
                counts_subquery.c.block_count,
                counts_subquery.c.skip_count,
                counts_subquery.c.last_executed_at,
                counts_subquery.c.last_updated_at,
            )
            .outerjoin(counts_subquery, counts_subquery.c.plan_case_id == PlanCase.id)
            .where(PlanCase.plan_id == plan_id)
        )

        if priorities:
            stmt = stmt.where(PlanCase.snapshot_priority.in_(list(priorities)))

        if include_value is not None:
            stmt = stmt.where(PlanCase.include.is_(include_value))

        if require_all_devices is not None:
            stmt = stmt.where(PlanCase.require_all_devices.is_(require_all_devices))

        if keyword:
            stmt = stmt.where(PlanCase.snapshot_title.ilike(f"%{keyword.strip()}%"))

        if device_model_id is not None:
            stmt = stmt.where(
                exists()
                .where(
                    ExecutionResult.plan_case_id == PlanCase.id,
                    ExecutionResult.device_model_id == device_model_id,
                )
                .correlate(PlanCase)
            )

        status_filters = set(statuses or [])
        for status in list(status_filters):
            validate_execution_result_status(status)
        if status_filters:
            stmt = stmt.where(aggregated_status_expr.in_(list(status_filters)))

        order_by = (order_by or "order_no").strip().lower()
        order_column = TestPlanService._resolve_case_order_column(order_by)
        stmt = stmt.order_by(order_column.asc(), PlanCase.id.asc())

        if cursor:
            cursor_value, cursor_id = TestPlanService._decode_cursor(cursor)
            typed_value = TestPlanService._cast_cursor_value(order_by, cursor_value)
            if typed_value is None:
                stmt = stmt.where(
                    or_(
                        and_(order_column.is_(None), PlanCase.id > cursor_id),
                        order_column.isnot(None),
                    )
                )
            else:
                stmt = stmt.where(
                    or_(
                        order_column > typed_value,
                        and_(order_column == typed_value, PlanCase.id > cursor_id),
                    )
                )

        stmt = stmt.limit(page_size + 1)
        rows = db.session.execute(stmt).all()

        has_more = len(rows) > page_size
        visible_rows = rows[:page_size]

        items: List[Dict] = []
        for row in visible_rows:
            mapping = row._mapping
            plan_case = mapping[PlanCase]
            result_summary = TestPlanService._build_result_summary_from_row(mapping)
            latest_result = TestPlanService._determine_case_latest_result(result_summary)
            last_executed_at = mapping.get("last_executed_at")
            last_updated_at = mapping.get("last_updated_at")
            result_summary["last_updated_at"] = (
                last_updated_at.isoformat() if last_updated_at else None
            )

            items.append(
                {
                    "id": plan_case.id,
                    "plan_id": plan_case.plan_id,
                    "case_id": plan_case.case_id,
                    "title": plan_case.snapshot_title,
                    "priority": plan_case.snapshot_priority,
                    "workload_minutes": plan_case.snapshot_workload_minutes,
                    "include": bool(plan_case.include),
                    "require_all_devices": bool(plan_case.require_all_devices),
                    "order_no": plan_case.order_no,
                    "group_path": plan_case.group_path_cache,
                    "latest_result": latest_result,
                    "result_summary": result_summary,
                    "last_executed_at": last_executed_at.isoformat() if last_executed_at else None,
                    "updated_at": plan_case.updated_at.isoformat() if plan_case.updated_at else None,
                }
            )

        next_cursor = None
        if has_more:
            next_mapping = rows[page_size]._mapping
            next_case = next_mapping[PlanCase]
            next_value = TestPlanService._extract_order_value(next_case, order_by)
            next_cursor = TestPlanService._encode_cursor(next_value, next_case.id)

        return {
            "items": items,
            "next_cursor": next_cursor,
            "page_size": page_size,
        }

    @staticmethod
    def get_plan_case_detail(
        plan_id: int,
        plan_case_id: int,
        *,
        includes: Optional[Iterable[str]] = None,
    ) -> Dict:
        include_set = TestPlanService._normalize_includes(includes)
        include_results = "execution_results" in include_set or "results" in include_set
        include_history = "history" in include_set
        include_attachments = "attachments" in include_set or include_history
        include_origin_case = "origin_case" in include_set or "test_case" in include_set

        options = []
        if include_origin_case:
            options.append(selectinload(PlanCase.origin_case))
        if include_results:
            base_loader = selectinload(PlanCase.execution_results)
            options.append(base_loader)
            options.append(
                selectinload(PlanCase.execution_results).selectinload(ExecutionResult.executor)
            )
            options.append(
                selectinload(PlanCase.execution_results).selectinload(ExecutionResult.plan_device_model)
            )
            options.append(
                selectinload(PlanCase.execution_results).selectinload(ExecutionResult.device_model)
            )
            if include_history:
                options.append(
                    selectinload(PlanCase.execution_results).selectinload(ExecutionResult.logs)
                )
            if include_attachments:
                options.append(
                    selectinload(PlanCase.execution_results).selectinload(ExecutionResult.attachments)
                )

        query = PlanCase.query.options(*options).filter(
            PlanCase.plan_id == plan_id,
            PlanCase.id == plan_case_id,
        )
        plan_case = query.first()
        if not plan_case:
            raise BizError("计划用例不存在", 404)

        summary = TestPlanService._query_case_result_summary(plan_case.id)

        data = {
            "id": plan_case.id,
            "plan_id": plan_case.plan_id,
            "case_id": plan_case.case_id,
            "title": plan_case.snapshot_title,
            "preconditions": plan_case.snapshot_preconditions,
            "steps": plan_case.snapshot_steps,
            "expected_result": plan_case.snapshot_expected_result,
            "priority": plan_case.snapshot_priority,
            "workload_minutes": plan_case.snapshot_workload_minutes,
            "include": bool(plan_case.include),
            "require_all_devices": bool(plan_case.require_all_devices),
            "order_no": plan_case.order_no,
            "group_path": plan_case.group_path_cache,
            "latest_result": summary["latest_result"],
            "result_summary": {
                "total": summary["total"],
                "executed": summary["executed"],
                "pending": summary["pending"],
                "passed": summary["passed"],
                "failed": summary["failed"],
                "blocked": summary["blocked"],
                "skipped": summary["skipped"],
                "last_updated_at": summary["last_updated_at"],
            },
            "last_executed_at": summary["last_executed_at"],
            "updated_at": plan_case.updated_at.isoformat() if plan_case.updated_at else None,
        }

        if include_origin_case and plan_case.origin_case:
            origin = plan_case.origin_case
            data["origin_case"] = {
                "id": origin.id,
                "title": origin.title,
                "priority": origin.priority,
                "status": origin.status,
                "workload_minutes": origin.workload_minutes,
                "preconditions": origin.preconditions,
                "steps": origin.steps,
                "expected_result": origin.expected_result,
            }

        if include_results:
            sorted_results = sorted(
                plan_case.execution_results,
                key=lambda result: (
                    result.run_id or 0,
                    result.device_model_id or 0,
                    result.id or 0,
                ),
            )
            data["execution_results"] = [
                result.to_dict(
                    include_history=include_history,
                    include_attachments=include_attachments,
                )
                for result in sorted_results
            ]

        return data

    @staticmethod
    def get_plan_statistics(plan_id: int) -> Dict:
        TestPlanService.get(
            plan_id,
            load_details=False,
            load_cases=False,
            load_device_models=False,
            load_testers=False,
            load_runs=False,
        )

        latest_run = (
            ExecutionRun.query
            .filter(ExecutionRun.plan_id == plan_id)
            .order_by(ExecutionRun.created_at.desc(), ExecutionRun.id.desc())
            .first()
        )

        stats = TestPlanService._build_statistics_from_run(latest_run)
        payload = {
            "plan_id": plan_id,
            "statistics": stats,
        }
        if latest_run:
            payload["run"] = TestPlanService._serialize_run_summary(latest_run)
        return payload

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
    def _normalize_includes(includes: Optional[Iterable[str]]) -> set[str]:
        if not includes:
            return set()
        if isinstance(includes, str):
            includes = includes.split(",")
        return {str(item).strip() for item in includes if str(item).strip()}

    @staticmethod
    def _build_case_result_summary_subquery(plan_id: int):
        fail_count_expr = func.sum(
            case((ExecutionResult.result == ExecutionResultStatus.FAIL.value, 1), else_=0)
        ).label("fail_count")
        block_count_expr = func.sum(
            case((ExecutionResult.result == ExecutionResultStatus.BLOCK.value, 1), else_=0)
        ).label("block_count")
        skip_count_expr = func.sum(
            case((ExecutionResult.result == ExecutionResultStatus.SKIP.value, 1), else_=0)
        ).label("skip_count")
        pending_count_expr = func.sum(
            case((ExecutionResult.result == ExecutionResultStatus.PENDING.value, 1), else_=0)
        ).label("pending_count")
        pass_count_expr = func.sum(
            case((ExecutionResult.result == ExecutionResultStatus.PASS.value, 1), else_=0)
        ).label("pass_count")
        executed_expr = func.sum(
            case((ExecutionResult.result != ExecutionResultStatus.PENDING.value, 1), else_=0)
        ).label("executed_results")

        subquery = (
            select(
                ExecutionResult.plan_case_id.label("plan_case_id"),
                func.count(ExecutionResult.id).label("total_results"),
                executed_expr,
                pending_count_expr,
                pass_count_expr,
                fail_count_expr,
                block_count_expr,
                skip_count_expr,
                func.max(ExecutionResult.executed_at).label("last_executed_at"),
                func.max(ExecutionResult.updated_at).label("last_updated_at"),
            )
            .join(PlanCase, PlanCase.id == ExecutionResult.plan_case_id)
            .where(PlanCase.plan_id == plan_id)
            .group_by(ExecutionResult.plan_case_id)
            .subquery()
        )
        return subquery

    @staticmethod
    def _build_result_summary_from_row(row_mapping) -> Dict[str, int]:
        total = int(row_mapping.get("total_results") or 0)
        pending = int(row_mapping.get("pending_count") or 0)
        executed = row_mapping.get("executed_results")
        if executed is None:
            executed = total - pending
        executed = int(executed)
        passed = int(row_mapping.get("pass_count") or 0)
        failed = int(row_mapping.get("fail_count") or 0)
        blocked = int(row_mapping.get("block_count") or 0)
        skipped = int(row_mapping.get("skip_count") or 0)
        return {
            "total": total,
            "executed": executed,
            "pending": pending,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
            "skipped": skipped,
        }

    @staticmethod
    def _determine_case_latest_result(summary: Mapping[str, int]) -> str:
        if summary.get("failed", 0) > 0:
            return ExecutionResultStatus.FAIL.value
        if summary.get("blocked", 0) > 0:
            return ExecutionResultStatus.BLOCK.value
        if summary.get("skipped", 0) > 0:
            return ExecutionResultStatus.SKIP.value
        if summary.get("pending", 0) > 0:
            return ExecutionResultStatus.PENDING.value
        return ExecutionResultStatus.PASS.value

    @staticmethod
    def _resolve_case_order_column(order_by: str):
        order_map = {
            "order_no": PlanCase.order_no,
            "priority": PlanCase.snapshot_priority,
            "title": PlanCase.snapshot_title,
            "updated_at": PlanCase.updated_at,
            "created_at": PlanCase.created_at,
            "id": PlanCase.id,
        }
        column = order_map.get(order_by)
        if column is None:
            raise BizError("order_by 参数不支持", 400)
        return column

    @staticmethod
    def _extract_order_value(plan_case: PlanCase, order_by: str):
        if order_by == "order_no":
            return plan_case.order_no
        if order_by == "priority":
            return plan_case.snapshot_priority
        if order_by == "title":
            return plan_case.snapshot_title
        if order_by == "created_at":
            return plan_case.created_at
        if order_by == "updated_at":
            return plan_case.updated_at
        if order_by == "id":
            return plan_case.id
        return plan_case.order_no

    @staticmethod
    def _encode_cursor(value, case_id: int) -> str:
        if isinstance(value, datetime):
            value = value.isoformat()
        payload = {"value": value, "id": case_id}
        encoded = json.dumps(payload, ensure_ascii=False, default=str)
        return base64.urlsafe_b64encode(encoded.encode("utf-8")).decode("utf-8")

    @staticmethod
    def _decode_cursor(cursor: str) -> Tuple[Optional[str], int]:
        try:
            decoded = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
            data = json.loads(decoded)
        except Exception as exc:  # noqa: BLE001
            raise BizError("cursor 参数不合法", 400) from exc

        if not isinstance(data, dict):
            raise BizError("cursor 参数不合法", 400)

        cursor_id = data.get("id")
        if cursor_id is None:
            raise BizError("cursor 参数不合法", 400)
        try:
            cursor_id = int(cursor_id)
        except (TypeError, ValueError) as exc:  # noqa: BLE001
            raise BizError("cursor 参数不合法", 400) from exc

        return data.get("value"), cursor_id

    @staticmethod
    def _cast_cursor_value(order_by: str, value):
        if value is None:
            return None
        if order_by in {"order_no", "id"}:
            try:
                return int(value)
            except (TypeError, ValueError) as exc:  # noqa: BLE001
                raise BizError("cursor 参数不合法", 400) from exc
        if order_by in {"priority", "title"}:
            return str(value)
        if order_by in {"created_at", "updated_at"}:
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value)
                except ValueError as exc:  # noqa: BLE001
                    raise BizError("cursor 参数不合法", 400) from exc
            raise BizError("cursor 参数不合法", 400)
        raise BizError("order_by 参数不支持", 400)

    @staticmethod
    def _query_case_result_summary(plan_case_id: int) -> Dict:
        stmt = select(
            func.count(ExecutionResult.id).label("total_results"),
            func.sum(
                case((ExecutionResult.result != ExecutionResultStatus.PENDING.value, 1), else_=0)
            ).label("executed_results"),
            func.sum(
                case((ExecutionResult.result == ExecutionResultStatus.PENDING.value, 1), else_=0)
            ).label("pending_count"),
            func.sum(
                case((ExecutionResult.result == ExecutionResultStatus.PASS.value, 1), else_=0)
            ).label("pass_count"),
            func.sum(
                case((ExecutionResult.result == ExecutionResultStatus.FAIL.value, 1), else_=0)
            ).label("fail_count"),
            func.sum(
                case((ExecutionResult.result == ExecutionResultStatus.BLOCK.value, 1), else_=0)
            ).label("block_count"),
            func.sum(
                case((ExecutionResult.result == ExecutionResultStatus.SKIP.value, 1), else_=0)
            ).label("skip_count"),
            func.max(ExecutionResult.executed_at).label("last_executed_at"),
            func.max(ExecutionResult.updated_at).label("last_updated_at"),
        ).where(ExecutionResult.plan_case_id == plan_case_id)

        result = db.session.execute(stmt).one()
        mapping = result._mapping
        summary_counts = TestPlanService._build_result_summary_from_row(mapping)
        latest_result = TestPlanService._determine_case_latest_result(summary_counts)
        last_executed_at = mapping.get("last_executed_at")
        last_updated_at = mapping.get("last_updated_at")

        return {
            "total": summary_counts["total"],
            "executed": summary_counts["executed"],
            "pending": summary_counts["pending"],
            "passed": summary_counts["passed"],
            "failed": summary_counts["failed"],
            "blocked": summary_counts["blocked"],
            "skipped": summary_counts["skipped"],
            "latest_result": latest_result,
            "last_executed_at": last_executed_at.isoformat() if last_executed_at else None,
            "last_updated_at": last_updated_at.isoformat() if last_updated_at else None,
        }

    @staticmethod
    def _parse_bool_arg(value: Optional[str], field_name: str) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        value_str = str(value).strip().lower()
        if value_str in {"true", "1", "yes", "y"}:
            return True
        if value_str in {"false", "0", "no", "n"}:
            return False
        raise BizError(f"{field_name} 参数必须是 true 或 false", 400)

    @staticmethod
    def _select_latest_run(runs: Iterable[ExecutionRun]) -> Optional[ExecutionRun]:
        runs = list(runs or [])
        if not runs:
            return None
        return max(
            runs,
            key=lambda run: (
                run.created_at or datetime.min,
                run.id or 0,
            ),
        )

    @staticmethod
    def _build_statistics_from_run(run: Optional[ExecutionRun]) -> Dict[str, int]:
        stats = {
            "total_results": 0,
            "executed_results": 0,
            "passed": 0,
            "failed": 0,
            "blocked": 0,
            "skipped": 0,
            "not_run": 0,
        }
        if not run:
            return stats

        stats.update(
            total_results=int(run.total or 0),
            executed_results=int(run.executed or 0),
            passed=int(run.passed or 0),
            failed=int(run.failed or 0),
            blocked=int(run.blocked or 0),
            skipped=int(run.skipped or 0),
            not_run=int(run.not_run or max((run.total or 0) - (run.executed or 0), 0)),
        )
        return stats

    @staticmethod
    def _serialize_tester_summary(tester: TestPlanTester) -> Dict:
        username = tester.tester.username if tester.tester else None
        return {
            "user_id": tester.user_id,
            "username": username,
        }

    @staticmethod
    def _serialize_device_summary(device: PlanDeviceModel) -> Dict:
        name = device.snapshot_name or (device.device_model.name if device.device_model else None)
        return {
            "id": device.id,
            "device_model_id": device.device_model_id,
            "name": name,
        }

    @staticmethod
    def _serialize_run_summary(run: ExecutionRun) -> Dict:
        return {
            "id": run.id,
            "name": run.name,
            "run_type": run.run_type,
            "status": run.status,
            "total": int(run.total or 0),
            "executed": int(run.executed or 0),
            "passed": int(run.passed or 0),
            "failed": int(run.failed or 0),
            "blocked": int(run.blocked or 0),
            "skipped": int(run.skipped or 0),
            "not_run": int(run.not_run or 0),
            "start_time": run.start_time.isoformat() if run.start_time else None,
            "end_time": run.end_time.isoformat() if run.end_time else None,
        }

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
    def _user_can_execute(plan: TestPlan, user) -> bool:
        if not user:
            return False
        if user.role in {Role.ADMIN.value, Role.DEPT_ADMIN.value, Role.PROJECT_ADMIN.value}:
            return True
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

