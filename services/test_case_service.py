# services/test_case_service.py
from typing import List, Optional, Tuple, Dict, Any
from models.test_case import TestCase
from models.user import User
from models.department import Department
from repositories.test_case_repository import TestCaseRepository, TestCaseHistoryRepository
from utils.exceptions import BizError
from constants.test_case import TestCasePriority, TestCaseStatus, TestCaseType
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
    """测试用例业务逻辑层"""

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
            created_by: int,
            preconditions: Optional[str] = None,
            steps: Optional[List[Dict]] = None,
            expected_result: Optional[str] = None,
            keywords: Optional[List[str]] = None,
            priority: str = TestCasePriority.P2.value,
            case_type: str = TestCaseType.FUNCTIONAL.value,
            group_id: Optional[int] = None,
            workload_minutes: Optional[int] = None
    ) -> TestCase:
        """创建测试用例"""
        # 验证参数
        if not title or not title.strip():
            raise BizError("用例标题不能为空", 400)

        validate_test_case_fields(priority=priority, case_type=case_type)

        # 验证步骤格式
        if steps:
            steps = TestCaseService.validate_steps(steps)

        # 验证部门是否存在
        department = Department.query.filter_by(id=department_id).first()
        if not department:
            raise BizError(f"部门ID {department_id} 不存在", 404)

        # 如果指定了分组，验证分组是否存在且属于该部门
        if group_id:
            from models.case_group import CaseGroup
            group = CaseGroup.query.filter_by(
                id=group_id,
                department_id=department_id,
                is_deleted=False
            ).first()
            if not group:
                raise BizError(f"分组ID {group_id} 不存在或不属于该部门", 404)

        # 创建用例
        test_case = TestCase(
            department_id=department_id,
            group_id=group_id,
            title=title.strip(),
            preconditions=preconditions,
            steps=steps or [],
            expected_result=expected_result,
            keywords=keywords or [],
            priority=priority,
            status=TestCaseStatus.ACTIVE.value,
            case_type=case_type,
            workload_minutes=workload_minutes,
            created_by=created_by,
            updated_by=created_by
        )

        # 保存到数据库
        test_case = TestCaseRepository.create(test_case)

        # 创建历史记录
        TestCaseHistoryRepository.create_history(
            test_case=test_case,
            change_type="CREATE",
            operated_by=created_by,
            change_summary="创建测试用例"
        )

        return test_case

    @staticmethod
    def get(case_id: int, user: User) -> TestCase:
        """获取测试用例详情"""
        test_case = TestCaseRepository.get_by_id(case_id)
        if not test_case:
            raise BizError("测试用例不存在", 404)

        # 验证用户权限
        assert_user_in_department(test_case.department_id, user)

        return test_case

    @staticmethod
    def update(
            case_id: int,
            user: User,
            **update_fields
    ) -> TestCase:
        """更新测试用例"""
        test_case = TestCaseRepository.get_by_id(case_id)
        if not test_case:
            raise BizError("测试用例不存在", 404)

        # 验证用户权限
        assert_user_in_department(test_case.department_id, user)

        # 记录变更的字段
        changed_fields = {}

        # 更新字段
        if "title" in update_fields:
            new_title = update_fields["title"]
            if not new_title or not new_title.strip():
                raise BizError("用例标题不能为空", 400)

            if test_case.title != new_title:
                changed_fields["title"] = {"old": test_case.title, "new": new_title}
                test_case.title = new_title.strip()

        if "preconditions" in update_fields:
            if test_case.preconditions != update_fields["preconditions"]:
                changed_fields["preconditions"] = {
                    "old": test_case.preconditions,
                    "new": update_fields["preconditions"]
                }
                test_case.preconditions = update_fields["preconditions"]

        if "steps" in update_fields:
            if test_case.steps != update_fields["steps"]:
                #changed_fields["steps"] = {"changed": True}
                changed_fields["steps"] = {
                    "old": test_case.steps,
                    "new": update_fields["steps"]
                }

                test_case.steps = update_fields["steps"]

        if "expected_result" in update_fields:
            if test_case.expected_result != update_fields["expected_result"]:
                changed_fields["expected_result"] = {
                    "old": test_case.expected_result,
                    "new": update_fields["expected_result"]
                }
                test_case.expected_result = update_fields["expected_result"]

        if "keywords" in update_fields:
            if test_case.keywords != update_fields["keywords"]:
                changed_fields["keywords"] = {
                    "old": test_case.keywords,
                    "new": update_fields["keywords"]
                }
                test_case.keywords = update_fields["keywords"]

        if "priority" in update_fields:
            priority = update_fields["priority"]
            validate_test_case_fields(priority=priority)
            if test_case.priority != priority:
                changed_fields["priority"] = {
                    "old": test_case.priority,
                    "new": priority
                }
                test_case.priority = priority

        if "status" in update_fields:
            status = update_fields["status"]
            validate_test_case_fields(status=status)
            if test_case.status != status:
                changed_fields["status"] = {
                    "old": test_case.status,
                    "new": status
                }
                test_case.status = status

        if "case_type" in update_fields:
            case_type = update_fields["case_type"]
            validate_test_case_fields(case_type=case_type)
            if test_case.case_type != case_type:
                changed_fields["case_type"] = {
                    "old": test_case.case_type,
                    "new": case_type
                }
                test_case.case_type = case_type

        if "workload_minutes" in update_fields:
            if test_case.workload_minutes != update_fields["workload_minutes"]:
                changed_fields["workload_minutes"] = {
                    "old": test_case.workload_minutes,
                    "new": update_fields["workload_minutes"]
                }
                test_case.workload_minutes = update_fields["workload_minutes"]

        if "group_id" in update_fields:
            if test_case.group_id != update_fields["group_id"]:
                changed_fields["group_id"] = {
                    "old": test_case.group_id,
                    "new": update_fields["group_id"]
                }
                test_case.group_id = update_fields["group_id"]

        # 如果没有任何变更，直接返回
        if not changed_fields:
            return test_case

        # 更新修改人
        test_case.updated_by = user.id

        # 保存更新
        test_case = TestCaseRepository.update(test_case)

        # 创建历史记录
        TestCaseHistoryRepository.create_history(
            test_case=test_case,
            change_type="UPDATE",
            operated_by=user.id,
            change_summary=f"更新了 {len(changed_fields)} 个字段",
            changed_fields=changed_fields
        )

        return test_case

    @staticmethod
    def delete(case_id: int, user: User) -> bool:
        """删除测试用例（软删除）"""
        test_case = TestCaseRepository.get_by_id(case_id)
        if not test_case:
            raise BizError("测试用例不存在", 404)

        # 验证用户权限
        assert_user_in_department(test_case.department_id, user)

        # 执行软删除
        success = TestCaseRepository.soft_delete(test_case, user.id)

        if success:
            # 创建历史记录
            TestCaseHistoryRepository.create_history(
                test_case=test_case,
                change_type="DELETE",
                operated_by=user.id,
                change_summary="删除测试用例"
            )

        return success

    @staticmethod
    def list(
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
        """查询测试用例列表"""
        return TestCaseRepository.list_by_department(
            department_id=department_id,
            title=title,
            status=status,
            priority=priority,
            case_type=case_type,
            keywords=keywords,
            group_id=group_id,
            page=page,
            page_size=page_size,
            order_by=order_by,
            order_desc=order_desc
        )

    @staticmethod
    def batch_delete(case_ids: List[int], department_id: int, user: User) -> int:
        """批量删除测试用例"""
        # 验证用户权限
        assert_user_in_department(department_id, user)

        if not case_ids:
            return 0

        # 执行批量软删除
        deleted_count = TestCaseRepository.batch_soft_delete(
            case_ids=case_ids,
            department_id=department_id,
            user_id=user.id
        )

        return deleted_count

    @staticmethod
    def batch_import(
            department_id: int,
            cases_data: List[Dict[str, Any]],
            user: User
    ) -> Dict[str, Any]:
        """批量导入测试用例"""
        assert_user_in_department(department_id, user)

        if not isinstance(cases_data, list):
            raise BizError("用例数据必须是数组", 400)

        if not cases_data:
            raise BizError("导入的用例数据不能为空", 400)

        created_cases: List[TestCase] = []
        errors: List[Dict[str, Any]] = []

        for index, case_payload in enumerate(cases_data, start=1):
            if not isinstance(case_payload, dict):
                errors.append({
                    "index": index,
                    "message": "用例数据必须是对象",
                    "code": 400
                })
                continue

            case_department_id = case_payload.get("department_id", department_id)
            if case_department_id != department_id:
                errors.append({
                    "index": index,
                    "title": case_payload.get("title"),
                    "message": "导入的用例部门与批量导入部门不一致",
                    "code": 400
                })
                continue

            try:
                test_case = TestCaseService.create(
                    department_id=case_department_id,
                    title=case_payload.get("title"),
                    created_by=user.id,
                    preconditions=case_payload.get("preconditions"),
                    steps=case_payload.get("steps"),
                    expected_result=case_payload.get("expected_result"),
                    keywords=case_payload.get("keywords"),
                    priority=case_payload.get("priority") or TestCasePriority.P2.value,
                    case_type=case_payload.get("case_type") or TestCaseType.FUNCTIONAL.value,
                    group_id=case_payload.get("group_id"),
                    workload_minutes=case_payload.get("workload_minutes")
                )
                created_cases.append(test_case)
            except BizError as exc:
                errors.append({
                    "index": index,
                    "title": case_payload.get("title"),
                    "message": exc.message,
                    "code": exc.code
                })
            except Exception as exc:  # pragma: no cover - 兜底保护
                errors.append({
                    "index": index,
                    "title": case_payload.get("title"),
                    "message": str(exc),
                    "code": 500
                })

        return {
            "created": created_cases,
            "errors": errors
        }

    @staticmethod
    def get_history(case_id: int, user: User, limit: int = 10) -> List[TestCaseRepository]:
        """获取测试用例的变更历史"""
        test_case = TestCaseRepository.get_by_id(case_id)
        if not test_case:
            raise BizError("测试用例不存在", 404)

        # 验证用户权限
        assert_user_in_department(test_case.department_id, user)

        return TestCaseHistoryRepository.get_histories(case_id, limit)
