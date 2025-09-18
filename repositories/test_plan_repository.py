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
from models.execution import ExecutionRun, ExecutionResult


class TestPlanRepository:
    """测试计划相关的持久化操作封装。"""

    @staticmethod
    def create(**kwargs) -> TestPlan:
        plan = TestPlan(**kwargs)
        db.session.add(plan)
        db.session.flush()
        return plan

    @staticmethod
    def get_by_id(plan_id: int, load_details: bool = True) -> Optional[TestPlan]:
        stmt = select(TestPlan)
        if load_details:
            stmt = stmt.options(
                selectinload(TestPlan.project).selectinload(Project.department),
                selectinload(TestPlan.creator),
                selectinload(TestPlan.plan_cases).selectinload(PlanCase.execution_results),
                selectinload(TestPlan.plan_device_models).selectinload(PlanDeviceModel.device_model),
                selectinload(TestPlan.plan_testers).selectinload(TestPlanTester.tester),
                selectinload(TestPlan.execution_runs).selectinload(ExecutionRun.execution_results),
            )
        stmt = stmt.where(TestPlan.id == plan_id)
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
    def commit():
        db.session.commit()

    @staticmethod
    def rollback():
        db.session.rollback()
