"""Data access helpers for legacy test tracking system tables."""
from __future__ import annotations

import math
from typing import List, Optional, Sequence

from sqlalchemy import text

from extensions.legacy_database import legacy_db


class LegacyDataRepository:
    """Raw SQL queries targeting the legacy database schema."""

    @staticmethod
    def list_projects(keyword: Optional[str] = None) -> List[str]:
        query = "SELECT DISTINCT project_name FROM TestPlan"
        params = {}
        if keyword:
            query += " WHERE project_name LIKE :keyword"
            params["keyword"] = f"%{keyword}%"
        query += " ORDER BY project_name"
        with legacy_db.connect() as conn:
            result = conn.execute(text(query), params)
            return [row[0] for row in result.fetchall()]

    @staticmethod
    def list_plans(project_name: str, keyword: Optional[str] = None) -> List[dict]:
        query = """
            SELECT id, plan_name
            FROM TestPlan
            WHERE project_name = :project_name
        """
        params = {"project_name": project_name}
        if keyword:
            query += " AND plan_name LIKE :keyword"
            params["keyword"] = f"%{keyword}%"
        query += " ORDER BY id"
        with legacy_db.connect() as conn:
            result = conn.execute(text(query), params)
            return [dict(row._mapping) for row in result.fetchall()]

    @staticmethod
    def list_models(plan_id: int) -> List[dict]:
        query = """
            SELECT m.ModelID AS model_id, m.ModelName AS model_name
            FROM model AS m
            JOIN testplanmodel AS tpm ON m.ModelID = tpm.ModelID
            WHERE tpm.PlanID = :plan_id
            ORDER BY m.ModelName
        """
        with legacy_db.connect() as conn:
            result = conn.execute(text(query), {"plan_id": plan_id})
            return [dict(row._mapping) for row in result.fetchall()]

    # --------- statistics helpers ---------
    @staticmethod
    def count_case_time(plan_id: int) -> int:
        query = """
            SELECT SUM(te.TestTime) AS total_time
            FROM TestExecution AS te
            INNER JOIN TestCase AS tc ON te.CaseID = tc.CaseID
            INNER JOIN TestSheet AS ts ON tc.sheet_id = ts.id
            WHERE ts.plan_id = :plan_id
        """
        with legacy_db.connect() as conn:
            result = conn.execute(text(query), {"plan_id": plan_id}).scalar()
        if result is None:
            return 0
        return int(math.ceil(result / 60.0))

    @staticmethod
    def count_workloading(plan_id: int) -> int:
        query = text(
            """
            SELECT SUM(CAST(SUBSTRING(workloading, 1, LENGTH(workloading) - 4) AS UNSIGNED))
            FROM TestSheet
            WHERE plan_id = :plan_id
            """
        )
        with legacy_db.connect() as conn:
            result = conn.execute(query, {"plan_id": plan_id}).scalar()
        return int(result) if result is not None else 0

    @staticmethod
    def count_case(plan_id: int) -> int:
        model_count_query = text(
            """
            SELECT COUNT(DISTINCT ModelID)
            FROM testplanmodel
            WHERE PlanID = :plan_id
            """
        )
        with legacy_db.connect() as conn:
            model_count = conn.execute(model_count_query, {"plan_id": plan_id}).scalar() or 0
            if model_count == 0:
                return 0
            case_count_query = text(
                """
                SELECT COUNT(*)
                FROM TestCase
                WHERE sheet_id IN (SELECT id FROM TestSheet WHERE plan_id = :plan_id)
                """
            )
            case_count = conn.execute(case_count_query, {"plan_id": plan_id}).scalar() or 0
        return int(case_count) * int(model_count)

    @staticmethod
    def count_executed_case(plan_id: int) -> int:
        query = text(
            """
            SELECT COUNT(te.CaseID)
            FROM TestExecution AS te
            INNER JOIN TestCase AS tc ON te.CaseID = tc.CaseID
            INNER JOIN TestSheet AS ts ON tc.sheet_id = ts.id
            WHERE ts.plan_id = :plan_id AND te.TestResult IS NOT NULL
            """
        )
        with legacy_db.connect() as conn:
            result = conn.execute(query, {"plan_id": plan_id}).scalar()
        return int(result) if result is not None else 0

    @staticmethod
    def count_test_case_results(plan_id: int) -> dict:
        query = text(
            """
            SELECT 
                SUM(CASE WHEN te.TestResult = 'Pass' THEN 1 ELSE 0 END) AS pass_count,
                SUM(CASE WHEN te.TestResult = 'Fail' THEN 1 ELSE 0 END) AS fail_count,
                SUM(CASE WHEN te.TestResult = 'Block' THEN 1 ELSE 0 END) AS block_count
            FROM testexecution AS te
            WHERE te.CaseID IN (
                SELECT tc.CaseID
                FROM TestCase AS tc
                WHERE tc.sheet_id IN (
                    SELECT ts.id FROM TestSheet AS ts WHERE ts.plan_id = :plan_id
                )
            )
            """
        )
        with legacy_db.connect() as conn:
            row = conn.execute(query, {"plan_id": plan_id}).fetchone()
        if row is None:
            return {"pass_count": 0, "fail_count": 0, "block_count": 0}
        mapping = row._mapping
        return {
            "pass_count": int(mapping.get("pass_count") or 0),
            "fail_count": int(mapping.get("fail_count") or 0),
            "block_count": int(mapping.get("block_count") or 0),
        }

    @staticmethod
    def list_testers(plan_id: int) -> List[str]:
        query = text(
            """
            SELECT DISTINCT te.executor_name
            FROM TestExecution AS te
            INNER JOIN TestCase AS tc ON te.CaseID = tc.CaseID
            INNER JOIN TestSheet AS ts ON tc.sheet_id = ts.id
            WHERE ts.plan_id = :plan_id AND te.executor_name IS NOT NULL AND te.executor_name <> ''
            ORDER BY te.executor_name
            """
        )
        with legacy_db.connect() as conn:
            result = conn.execute(query, {"plan_id": plan_id}).fetchall()
        return [row[0] for row in result]

    @staticmethod
    def list_sheets(plan_id: int) -> List[dict]:
        query = text(
            """
            SELECT id, sheet_name
            FROM TestSheet
            WHERE plan_id = :plan_id
            ORDER BY id
            """
        )
        with legacy_db.connect() as conn:
            result = conn.execute(query, {"plan_id": plan_id}).fetchall()
        return [dict(row._mapping) for row in result]

    @staticmethod
    def list_case_status(model_id: int, sheet_id: int) -> List[dict]:
        query = text(
            """
            SELECT
                te.executor_name,
                te.TestResult,
                te.TestTime,
                te.StartTime,
                te.EndTime,
                GROUP_CONCAT(CONCAT(IFNULL(tcc.CommentTime, 'N/A'), ': ', IFNULL(tcc.Comment, 'No Comment')) ORDER BY tcc.CommentTime ASC SEPARATOR '\n') AS Comments,
                tc.CaseTitle,
                tc.PreConditions,
                tc.CaseSteps,
                tc.ExpectedResult,
                te.ExecutionID,
                te.ModelID,
                tc.CaseID,
                tc.sheet_id,
                te.FailCount,
                te.BlockCount
            FROM TestCase AS tc
            LEFT JOIN TestExecution AS te ON te.CaseID = tc.CaseID AND te.ModelID = :model_id
            LEFT JOIN TestCaseComments AS tcc ON tcc.ExecutionID = te.ExecutionID
            WHERE tc.sheet_id = :sheet_id
            GROUP BY tc.CaseID
            ORDER BY tc.CaseID
            """
        )
        params = {"model_id": model_id, "sheet_id": sheet_id}
        with legacy_db.connect() as conn:
            result = conn.execute(query, params).fetchall()
        return [dict(row._mapping) for row in result]

    @staticmethod
    def list_images(execution_ids: Sequence[int]) -> List[dict]:
        if not execution_ids:
            return []
        placeholders = ", ".join(f":id_{idx}" for idx, _ in enumerate(execution_ids))
        query = text(
            f"""
            SELECT *
            FROM testcase_image
            WHERE ExecutionID IN ({placeholders})
            """
        )
        params = {f"id_{idx}": execution_id for idx, execution_id in enumerate(execution_ids)}
        with legacy_db.connect() as conn:
            result = conn.execute(query, params).fetchall()
        return [dict(row._mapping) for row in result]
