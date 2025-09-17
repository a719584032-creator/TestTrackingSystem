# -*- coding: utf-8 -*-
"""services/test_plan_service.py
--------------------------------------------------------------------
测试计划业务逻辑实现。
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from constants.roles import Role
from constants.test_plan import (
    DEFAULT_PLAN_STATUS,
    ExecutionResultStatus,
    TestPlanStatus,
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
from models.execution import ExecutionRun, ExecutionResult
from repositories.case_group_repository import CaseGroupRepository
from repositories.device_model_repository import DeviceModelRepository
from repositories.project_repository import ProjectRepository
from repositories.test_plan_repository import TestPlanRepository
from utils.exceptions import BizError
from utils.permissions import assert_user_in_department


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
            plan_device = PlanDeviceModel(plan_id=plan.id, device_model_id=device.id)
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
    def get(plan_id: int) -> TestPlan:
        plan = TestPlanRepository.get_by_id(plan_id)
        if not plan:
            raise BizError("测试计划不存在", 404)
        return plan

    @staticmethod
    def list(
        *,
        project_id: Optional[int] = None,
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
        duration_ms: Optional[int] = None,
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

        execution_result.result = result
        execution_result.executed_by = current_user.id if current_user else None
        execution_result.executed_at = datetime.utcnow()
        execution_result.remark = remark
        execution_result.failure_reason = failure_reason
        execution_result.bug_ref = bug_ref
        execution_result.duration_ms = duration_ms

        TestPlanService._refresh_statistics(plan)
        TestPlanRepository.commit()
        return execution_result

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

