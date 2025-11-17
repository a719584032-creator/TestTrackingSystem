# repositories/test_case_repository.py
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import and_, or_, desc, asc
from extensions.database import db
from models.test_case import TestCase
from models.test_case_history import TestCaseHistory
from datetime import datetime


class TestCaseRepository:
    """测试用例数据访问层"""

    @staticmethod
    def create(test_case: TestCase) -> TestCase:
        """创建测试用例"""
        db.session.add(test_case)
        db.session.commit()
        return test_case

    @staticmethod
    def get_by_id(case_id: int, include_deleted: bool = False) -> Optional[TestCase]:
        """根据ID获取测试用例"""
        query = TestCase.query.filter_by(id=case_id)
        if not include_deleted:
            query = query.filter_by(is_deleted=False)
        return query.first()

    @staticmethod
    def update(test_case: TestCase) -> TestCase:
        """更新测试用例"""
        test_case.increment_version()  # 使用 VersionMixin 的方法
        db.session.commit()
        return test_case

    @staticmethod
    def soft_delete(test_case: TestCase, user_id: int) -> bool:
        """软删除测试用例"""
        test_case.soft_delete(user_id=user_id)  # 使用 SoftDeleteMixin 的方法
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
            group_id: Optional[int] = None,
            page: int = 1,
            page_size: int = 20,
            order_by: str = "created_at",
            order_desc: bool = True
    ) -> Tuple[List[TestCase], int]:
        """分页查询部门下的测试用例"""
        query = TestCase.query_active().filter_by(department_id=department_id)

        # 应用过滤条件
        if title:
            query = query.filter(TestCase.title.contains(title))
        if status:
            query = query.filter_by(status=status)
        if priority:
            query = query.filter_by(priority=priority)
        if case_type:
            query = query.filter_by(case_type=case_type)
        if group_id:
            query = query.filter_by(group_id=group_id)

        # 关键字过滤（JSON字段）
        if keywords:
            for keyword in keywords:
                query = query.filter(TestCase.keywords.contains(keyword))

        # 排序
        order_column = getattr(TestCase, order_by, TestCase.created_at)
        if order_desc:
            query = query.order_by(desc(order_column))
        else:
            query = query.order_by(asc(order_column))

        # 分页
        paginate = query.paginate(page=page, per_page=page_size, error_out=False)

        return paginate.items, paginate.total

    @staticmethod
    def batch_soft_delete(case_ids: List[int], department_id: int, user_id: int) -> int:
        """批量软删除测试用例"""
        affected = TestCase.query.filter(
            and_(
                TestCase.id.in_(case_ids),
                TestCase.department_id == department_id,
                TestCase.is_deleted == False
            )
        ).update(
            {
                "is_deleted": True,
                "deleted_at": datetime.utcnow(),
                "deleted_by": user_id
            },
            synchronize_session=False
        )
        db.session.commit()
        return affected

    @staticmethod
    def exists_by_title(department_id: int, title: str, exclude_id: Optional[int] = None) -> bool:
        """检查标题是否已存在"""
        query = TestCase.query_active().filter_by(
            department_id=department_id,
            title=title
        )
        if exclude_id:
            query = query.filter(TestCase.id != exclude_id)
        return query.first() is not None


class TestCaseHistoryRepository:
    """测试用例历史记录数据访问层"""

    @staticmethod
    def create_history(
            test_case: TestCase,
            change_type: str,
            operated_by: int,
            change_summary: Optional[str] = None,
            changed_fields: Optional[Dict[str, Any]] = None
    ) -> TestCaseHistory:
        """创建历史记录"""
        history = TestCaseHistory(
            test_case_id=test_case.id,
            version=test_case.version,
            title=test_case.title,
            preconditions=test_case.preconditions,
            steps=test_case.steps,
            expected_result=test_case.expected_result,
            keywords=test_case.keywords,
            priority=test_case.priority,
            status=test_case.status,
            case_type=test_case.case_type,
            workload_minutes=test_case.workload_minutes,
            change_type=change_type,
            change_summary=change_summary,
            changed_fields=changed_fields,
            operated_by=operated_by,
            operated_at=datetime.utcnow()
        )
        db.session.add(history)
        db.session.commit()
        return history

    @staticmethod
    def get_histories(test_case_id: int, limit: int = 10) -> List[TestCaseHistory]:
        """获取测试用例的历史记录"""
        return TestCaseHistory.query.filter_by(
            test_case_id=test_case_id
        ).order_by(desc(TestCaseHistory.version)).limit(limit).all()
