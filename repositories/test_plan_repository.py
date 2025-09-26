from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import selectinload

from extensions.database import db
from models.project import Project
from models.test_plan import TestPlan
from models.plan_case import PlanCase
from models.plan_device_model import PlanDeviceModel
from models.plan_tester import TestPlanTester
from models.execution import ExecutionRun, ExecutionResult, ExecutionResultLog


class TestPlanRepository:
    """测试计划相关的持久化操作封装。"""

    @staticmethod
    def create(**kwargs) -> TestPlan:
        plan = TestPlan(**kwargs)
        db.session.add(plan)
        db.session.flush()
        return plan

    @staticmethod
    def get_by_id(
        plan_id: int,
        *,
        load_project: bool = True,
        load_creator: bool = True,
        load_cases: bool = True,
        load_case_results: bool = True,
        load_case_result_logs: bool = True,
        load_case_result_log_attachments: bool = True,
        load_case_result_attachments: bool = True,
        load_device_models: bool = True,
        load_testers: bool = True,
        load_execution_runs: bool = True,
        load_execution_run_results: bool = True,
    ) -> Optional[TestPlan]:
        stmt = select(TestPlan)
        options = []

        if load_project:
            options.append(selectinload(TestPlan.project).selectinload(Project.department))
        if load_creator:
            options.append(selectinload(TestPlan.creator))
        if load_device_models:
            options.append(
                selectinload(TestPlan.plan_device_models).selectinload(PlanDeviceModel.device_model)
            )
        if load_testers:
            options.append(selectinload(TestPlan.plan_testers).selectinload(TestPlanTester.tester))
        if load_execution_runs:
            run_loader = selectinload(TestPlan.execution_runs)
            if load_execution_run_results:
                run_loader = run_loader.selectinload(ExecutionRun.execution_results)
            options.append(run_loader)
        if load_cases:
            case_loader = selectinload(TestPlan.plan_cases)
            if load_case_results:
                case_loader = case_loader.selectinload(PlanCase.execution_results)
                if load_case_result_attachments:
                    case_loader = case_loader.selectinload(ExecutionResult.attachments)
                if load_case_result_logs:
                    case_loader = case_loader.selectinload(ExecutionResult.logs)
                    if load_case_result_log_attachments:
                        case_loader = case_loader.selectinload(ExecutionResultLog.attachments)
            options.append(case_loader)

        if options:
            stmt = stmt.options(*options)

        stmt = stmt.where(TestPlan.id == plan_id)
        return db.session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_plan_case(
        plan_id: int,
        plan_case_id: int,
        *,
        include_results: bool = True,
        include_result_logs: bool = True,
        include_result_log_attachments: bool = True,
        include_result_attachments: bool = True,
    ) -> Optional[PlanCase]:
        stmt = select(PlanCase)
        options = []

        if include_results:
            result_loader = selectinload(PlanCase.execution_results)
            if include_result_attachments:
                result_loader = result_loader.selectinload(ExecutionResult.attachments)
            if include_result_logs:
                result_loader = result_loader.selectinload(ExecutionResult.logs)
                if include_result_log_attachments:
                    result_loader = result_loader.selectinload(ExecutionResultLog.attachments)
            options.append(result_loader)

        if options:
            stmt = stmt.options(*options)

        stmt = stmt.where(PlanCase.plan_id == plan_id, PlanCase.id == plan_case_id)
        return db.session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list(
        project_id: Optional[int] = None,
        department_id: Optional[int] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        order_desc: bool = True,
    ) -> Tuple[List[TestPlan], int]:
        stmt = select(TestPlan).options(
            selectinload(TestPlan.project).selectinload(Project.department),
            selectinload(TestPlan.plan_device_models).selectinload(PlanDeviceModel.device_model),
            selectinload(TestPlan.plan_testers).selectinload(TestPlanTester.tester),
        )
        count_stmt = select(func.count(TestPlan.id))

        conditions = []
        if project_id:
            conditions.append(TestPlan.project_id == project_id)
        if department_id:
            conditions.append(TestPlan.project.has(Project.department_id == department_id))
        if status:
            conditions.append(TestPlan.status == status)
        if keyword:
            conditions.append(TestPlan.name.ilike(f"%{keyword.strip()}%"))
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        stmt = stmt.order_by(desc(TestPlan.created_at) if order_desc else asc(TestPlan.created_at))
        total = db.session.execute(count_stmt).scalar() or 0
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = db.session.execute(stmt).scalars().all()
        return items, total

    @staticmethod
    def delete(plan: TestPlan):
        db.session.delete(plan)

    @staticmethod
    def add_plan_case(plan_case: PlanCase):
        db.session.add(plan_case)

    @staticmethod
    def add_plan_device_model(plan_device_model: PlanDeviceModel):
        db.session.add(plan_device_model)

    @staticmethod
    def add_plan_tester(plan_tester: TestPlanTester):
        db.session.add(plan_tester)

    @staticmethod
    def add_execution_run(run: ExecutionRun):
        db.session.add(run)

    @staticmethod
    def add_execution_result(result: ExecutionResult):
        db.session.add(result)

    @staticmethod
    def add_execution_result_log(log: ExecutionResultLog):
        db.session.add(log)

    @staticmethod
    def commit():
        db.session.commit()

    @staticmethod
    def rollback():
        db.session.rollback()
