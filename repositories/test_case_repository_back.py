# repositories/test_case_repository.py
from typing import List, Optional, Tuple
from sqlalchemy import and_, or_, func
from extensions.database import db
from models.test_case import TestCase
from models.test_case_history import TestCaseHistory
from models.case_group import CaseGroup


class TestCaseRepository:
    @staticmethod
    def create(
            department_id: int,
            title: str,
            preconditions: Optional[str] = None,
            steps: Optional[List[dict]] = None,
            expected_result: Optional[str] = None,
            keywords: Optional[List[str]] = None,
            priority: str = "P2",
            status: str = "active",
            case_type: str = "functional",
            created_by: Optional[int] = None,
    ) -> TestCase:
        """创建测试用例"""
        test_case = TestCase(
            department_id=department_id,
            title=title,
            preconditions=preconditions,
            steps=steps or [],
            expected_result=expected_result,
            keywords=keywords or [],
            priority=priority,
            status=status,
            case_type=case_type,
            created_by=created_by,
            updated_by=created_by,
        )
        db.session.add(test_case)
        db.session.commit()
        return test_case

    @staticmethod
    def get_by_id(case_id: int) -> Optional[TestCase]:
        """根据ID获取测试用例"""
        return db.session.query(TestCase).filter_by(id=case_id).first()

    @staticmethod
    def update(
            case_id: int,
            title: Optional[str] = None,
            preconditions: Optional[str] = None,
            steps: Optional[List[dict]] = None,
            expected_result: Optional[str] = None,
            keywords: Optional[List[str]] = None,
            priority: Optional[str] = None,
            status: Optional[str] = None,
            case_type: Optional[str] = None,
            updated_by: Optional[int] = None,
    ) -> Optional[TestCase]:
        """更新测试用例"""
        test_case = TestCaseRepository.get_by_id(case_id)
        if not test_case:
            return None

        if title is not None:
            test_case.title = title
        if preconditions is not None:
            test_case.preconditions = preconditions
        if steps is not None:
            test_case.steps = steps
        if expected_result is not None:
            test_case.expected_result = expected_result
        if keywords is not None:
            test_case.keywords = keywords
        if priority is not None:
            test_case.priority = priority
        if status is not None:
            test_case.status = status
        if case_type is not None:
            test_case.case_type = case_type
        if updated_by is not None:
            test_case.updated_by = updated_by

        db.session.commit()
        return test_case

    @staticmethod
    def delete(case_id: int) -> bool:
        """删除测试用例"""
        test_case = TestCaseRepository.get_by_id(case_id)
        if not test_case:
            return False

        db.session.delete(test_case)
        db.session.commit()
        return True

    @staticmethod
    def list_by_department(
            department_id: int,
            title: Optional[str] = None,
            status: Optional[str] = None,
            priority: Optional[str] = None,
            case_type: Optional[str] = None,
            keywords: Optional[List[str]] = None,
            project_id: Optional[int] = None,
            group_id: Optional[int] = None,
            page: int = 1,
            page_size: int = 20,
            order_by: str = "created_at",
            order_desc: bool = True,
    ) -> Tuple[List[TestCase], int]:
        """获取部门下的测试用例列表"""
        query = db.session.query(TestCase).filter_by(department_id=department_id)

        # 筛选条件
        if title:
            query = query.filter(TestCase.title.contains(title))
        if status:
            query = query.filter_by(status=status)
        if priority:
            query = query.filter_by(priority=priority)
        if case_type:
            query = query.filter_by(case_type=case_type)

        # 关键字筛选（包含任意一个关键字）
        if keywords:
            keyword_conditions = []
            for keyword in keywords:
                keyword_conditions.append(
                    func.json_contains(TestCase.keywords, f'"{keyword}"')
                )
            query = query.filter(or_(*keyword_conditions))

        # 项目和分组筛选
        if project_id or group_id:
            query = query.join(TestCaseHistory)
            if project_id:
                query = query.filter(TestCaseHistory.project_id == project_id)
            if group_id:
                query = query.filter(TestCaseHistory.group_id == group_id)

        # 排序
        order_column = getattr(TestCase, order_by, TestCase.created_at)
        if order_desc:
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())

        # 分页
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()

        return items, total

    @staticmethod
    def batch_delete(case_ids: List[int], department_id: int) -> int:
        """批量删除测试用例"""
        deleted_count = db.session.query(TestCase).filter(
            TestCase.id.in_(case_ids),
            TestCase.department_id == department_id
        ).delete(synchronize_session=False)
        db.session.commit()
        return deleted_count
