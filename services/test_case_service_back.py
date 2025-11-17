# services/test_case_service.py
from typing import List, Optional, Tuple, Dict, Any
from extensions.database import db
from repositories.test_case_repository import TestCaseRepository
from repositories.department_member_repository import DepartmentMemberRepository
from models.test_case import TestCase
from models.user import User
from utils.exceptions import BizError
from utils.permissions import assert_user_in_department
from constants.test_case import (
    TestCasePriority,
    TestCaseStatus,
    TestCaseType,
    validate_priority,
    validate_case_type,
    validate_status,
    validate_test_case_fields
)


class TestCaseService:
    @staticmethod
    def validate_steps(steps: List[dict]) -> List[dict]:
        """验证步骤格式"""
        if not isinstance(steps, list):
            raise BizError("步骤必须是数组格式", 400)

        validated_steps = []
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                raise BizError(f"第{i + 1}个步骤格式错误", 400)

            # 验证必填字段
            if "action" not in step or not step["action"].strip():
                raise BizError(f"第{i + 1}个步骤缺少action字段", 400)

            validated_step = {
                "no": step.get("no", i + 1),
                "action": step["action"].strip(),
                "keyword": step.get("keyword", "").strip(),
                "note": step.get("note", "").strip(),
                "expected": step.get("expected", "").strip()
            }
            validated_steps.append(validated_step)

        return validated_steps

    @staticmethod
    def create(
            department_id: int,
            title: str,
            preconditions: Optional[str] = None,
            steps: Optional[List[dict]] = None,
            expected_result: Optional[str] = None,
            keywords: Optional[List[str]] = None,
            priority: str = TestCasePriority.P2.value,
            case_type: str = TestCaseType.FUNCTIONAL.value,
            created_by: Optional[int] = None,
            project_ids: Optional[List[int]] = None,
            group_mappings: Optional[Dict[int, int]] = None
    ) -> TestCase:
        """创建测试用例"""
        # 验证参数
        if not title or not title.strip():
            raise BizError("用例标题不能为空", 400)

        validate_test_case_fields(priority=priority, case_type=case_type)

        # 验证步骤格式
        if steps:
            steps = TestCaseService.validate_steps(steps)

        # 创建用例
        test_case = TestCaseRepository.create(
            department_id=department_id,
            title=title.strip(),
            preconditions=preconditions,
            steps=steps or [],
            expected_result=expected_result,
            keywords=keywords or [],
            priority=priority,
            status=TestCaseStatus.ACTIVE.value,
            case_type=case_type,
            created_by=created_by
        )

        # 关联到项目
        if project_ids:
            for project_id in project_ids:
                group_id = group_mappings.get(project_id) if group_mappings else None
                TestCaseProjectRepository.create(
                    test_case_id=test_case.id,
                    project_id=project_id,
                    group_id=group_id
                )

        return test_case

    @staticmethod
    def update(
            case_id: int,
            user: User,
            **kwargs
    ) -> TestCase:
        """更新测试用例"""
        test_case = TestCaseRepository.get_by_id(case_id)
        if not test_case:
            raise BizError("测试用例不存在", 404)

        # 权限检查
        assert_user_in_department(test_case.department_id, user)

        # 验证步骤格式
        if "steps" in kwargs and kwargs["steps"] is not None:
            kwargs["steps"] = TestCaseService.validate_steps(kwargs["steps"])

        # 如果提供了就校验
        if "priority" in kwargs and kwargs["priority"] is not None:
            validate_priority(kwargs["priority"])
        if "status" in kwargs and kwargs["status"] is not None:
            validate_status(kwargs["status"])
        if "case_type" in kwargs and kwargs["case_type"] is not None:
            validate_case_type(kwargs["case_type"])

        kwargs["updated_by"] = user.id

        updated_case = TestCaseRepository.update(case_id, **kwargs)
        if not updated_case:
            raise BizError("更新失败", 500)

        return updated_case

    @staticmethod
    def delete(case_id: int, user: User) -> bool:
        """删除测试用例"""
        test_case = TestCaseRepository.get_by_id(case_id)
        if not test_case:
            raise BizError("测试用例不存在", 404)

        # 权限检查
        assert_user_in_department(test_case.department_id, user)

        return TestCaseRepository.delete(case_id)

    @staticmethod
    def get(case_id: int, user: User) -> TestCase:
        """获取测试用例详情"""
        test_case = TestCaseRepository.get_by_id(case_id)
        if not test_case:
            raise BizError("测试用例不存在", 404)

        # 权限检查
        assert_user_in_department(test_case.department_id, user)

        return test_case

    @staticmethod
    def list(
            department_id: int,
            **filters
    ) -> Tuple[List[TestCase], int]:
        """获取测试用例列表"""

        return TestCaseRepository.list_by_department(
            department_id=department_id,
            **filters
        )

    @staticmethod
    def batch_delete(
            case_ids: List[int],
            department_id: int,
    ) -> int:
        """批量删除测试用例"""

        return TestCaseRepository.batch_delete(case_ids, department_id)

    @staticmethod
    def link_to_project(
            case_id: int,
            project_id: int,
            group_id: Optional[int],
            user: User
    ) -> None:
        """将用例关联到项目"""
        test_case = TestCaseRepository.get_by_id(case_id)
        if not test_case:
            raise BizError("测试用例不存在", 404)

        # 权限检查
        assert_user_in_department(test_case.department_id, user)

        # 检查是否已关联
        existing = TestCaseProjectRepository.get_by_case_and_project(
            case_id, project_id
        )
        if existing:
            raise BizError("用例已关联到该项目", 400)

        TestCaseProjectRepository.create(
            test_case_id=case_id,
            project_id=project_id,
            group_id=group_id
        )

    @staticmethod
    def unlink_from_project(
            case_id: int,
            project_id: int,
            user: User
    ) -> bool:
        """将用例从项目中移除"""
        test_case = TestCaseRepository.get_by_id(case_id)
        if not test_case:
            raise BizError("测试用例不存在", 404)

        # 权限检查
        assert_user_in_department(test_case.department_id, user)

        return TestCaseProjectRepository.delete(case_id, project_id)
