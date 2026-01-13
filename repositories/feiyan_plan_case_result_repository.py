# -*- coding: utf-8 -*-
"""feiyan_plan_case_result_repository.py
--------------------------------------------------------------------
飞雁导入用例与结果数据访问封装。
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import func, select

from extensions.database import db
from models.feiyan_plan_case_result import FeiyanPlanCaseResult


class FeiyanPlanCaseResultRepository:
    @staticmethod
    def get_by_case_id(case_id_ext: str) -> Optional[FeiyanPlanCaseResult]:
        if not case_id_ext:
            return None
        return FeiyanPlanCaseResult.query.filter_by(case_id_ext=case_id_ext).first()

    @staticmethod
    def get_by_plan_and_case(
        plan_id_ext: str,
        case_id_ext: str,
    ) -> Optional[FeiyanPlanCaseResult]:
        if not plan_id_ext or not case_id_ext:
            return None
        return (
            FeiyanPlanCaseResult.query
            .filter(
                FeiyanPlanCaseResult.plan_id_ext == plan_id_ext,
                FeiyanPlanCaseResult.case_id_ext == case_id_ext,
            )
            .first()
        )

    @staticmethod
    def list_by_plan(
        *,
        plan_id_ext: str,
        keyword: Optional[str] = None,
        group_path: Optional[str] = None,
        priority: Optional[str] = None,
        run_result: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[FeiyanPlanCaseResult], int]:
        stmt = select(FeiyanPlanCaseResult).where(
            FeiyanPlanCaseResult.plan_id_ext == plan_id_ext
        )
        count_stmt = select(func.count(FeiyanPlanCaseResult.id)).where(
            FeiyanPlanCaseResult.plan_id_ext == plan_id_ext
        )

        if keyword:
            stmt = stmt.where(FeiyanPlanCaseResult.case_title.ilike(f"%{keyword}%"))
            count_stmt = count_stmt.where(FeiyanPlanCaseResult.case_title.ilike(f"%{keyword}%"))
        if group_path:
            stmt = stmt.where(FeiyanPlanCaseResult.group_path == group_path)
            count_stmt = count_stmt.where(FeiyanPlanCaseResult.group_path == group_path)
        if priority:
            stmt = stmt.where(FeiyanPlanCaseResult.priority == priority)
            count_stmt = count_stmt.where(FeiyanPlanCaseResult.priority == priority)
        if run_result:
            stmt = stmt.where(FeiyanPlanCaseResult.run_result == run_result)
            count_stmt = count_stmt.where(FeiyanPlanCaseResult.run_result == run_result)

        total = db.session.execute(count_stmt).scalar() or 0
        stmt = (
            stmt.order_by(FeiyanPlanCaseResult.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = db.session.execute(stmt).scalars().all()
        return items, total

    @staticmethod
    def list_ids_by_plan(plan_id_ext: str) -> List[str]:
        rows = (
            db.session.query(FeiyanPlanCaseResult.case_id_ext)
            .filter(FeiyanPlanCaseResult.plan_id_ext == plan_id_ext)
            .all()
        )
        return [row[0] for row in rows]

    @staticmethod
    def add(case_result: FeiyanPlanCaseResult):
        db.session.add(case_result)

    @staticmethod
    def commit():
        db.session.commit()

    @staticmethod
    def rollback():
        db.session.rollback()
