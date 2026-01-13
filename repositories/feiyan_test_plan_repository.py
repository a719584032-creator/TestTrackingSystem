# -*- coding: utf-8 -*-
"""feiyan_test_plan_repository.py
--------------------------------------------------------------------
飞雁测试计划数据访问封装。
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import func, select

from extensions.database import db
from models.feiyan_test_plan import FeiyanTestPlan


class FeiyanTestPlanRepository:
    @staticmethod
    def get_by_plan_id(plan_id_ext: str) -> Optional[FeiyanTestPlan]:
        if not plan_id_ext:
            return None
        return FeiyanTestPlan.query.get(plan_id_ext)

    @staticmethod
    def list_departments(page: int, page_size: int) -> Tuple[List[dict], int]:
        base = db.session.query(
            FeiyanTestPlan.dept_id_ext,
            FeiyanTestPlan.dept_name,
        ).distinct()

        total = db.session.query(
            func.count(func.distinct(FeiyanTestPlan.dept_id_ext))
        ).scalar() or 0

        rows = (
            base.order_by(FeiyanTestPlan.dept_id_ext.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = [
            {"department_id": dept_id, "department_name": dept_name}
            for dept_id, dept_name in rows
        ]
        return items, total

    @staticmethod
    def list_plans(
        *,
        dept_id_ext: Optional[str] = None,
        project_id_ext: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[FeiyanTestPlan], int]:
        stmt = select(FeiyanTestPlan)
        count_stmt = select(func.count(FeiyanTestPlan.plan_id_ext))

        if dept_id_ext:
            stmt = stmt.where(FeiyanTestPlan.dept_id_ext == dept_id_ext)
            count_stmt = count_stmt.where(FeiyanTestPlan.dept_id_ext == dept_id_ext)
        if project_id_ext:
            stmt = stmt.where(FeiyanTestPlan.project_id_ext == project_id_ext)
            count_stmt = count_stmt.where(FeiyanTestPlan.project_id_ext == project_id_ext)

        total = db.session.execute(count_stmt).scalar() or 0
        stmt = (
            stmt.order_by(FeiyanTestPlan.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = db.session.execute(stmt).scalars().all()
        return items, total

    @staticmethod
    def add(plan: FeiyanTestPlan):
        db.session.add(plan)

    @staticmethod
    def commit():
        db.session.commit()

    @staticmethod
    def rollback():
        db.session.rollback()
