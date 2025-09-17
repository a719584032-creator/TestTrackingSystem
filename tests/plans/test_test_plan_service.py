import pytest

from app import create_app
from constants.roles import Role
from constants.test_plan import ExecutionResultStatus, TestPlanStatus
from extensions.database import db
from models.department import Department, DepartmentMember
from models.device_model import DeviceModel
from models.project import Project
from models.test_case import TestCase
from models.user import User
from services.test_plan_service import TestPlanService
from utils.exceptions import BizError


@pytest.fixture(scope="module")
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def seed_data(app):
    with app.app_context():
        db.session.query(DepartmentMember).delete()
        db.session.query(TestCase).delete()
        db.session.query(DeviceModel).delete()
        db.session.query(Project).delete()
        db.session.query(Department).delete()
        db.session.query(User).delete()
        db.session.commit()

        dept = Department(name="质量部", code="QA", description="测试部门")
        admin = User(username="admin_user", password_hash="hash", role=Role.ADMIN.value)
        tester = User(username="tester_user", password_hash="hash", role=Role.USER.value)
        db.session.add_all([dept, admin, tester])
        db.session.flush()

        db.session.add(DepartmentMember(department_id=dept.id, user_id=tester.id))
        project = Project(
            department_id=dept.id,
            name="项目A",
            code="PROJ_A",
            status="active",
        )
        db.session.add(project)

        device1 = DeviceModel(department_id=dept.id, name="Android", model_code="A1")
        device2 = DeviceModel(department_id=dept.id, name="iOS", model_code="I1")
        db.session.add_all([device1, device2])

        case1 = TestCase(
            department_id=dept.id,
            title="登录功能",
            steps=[],
            keywords=[],
            priority="P1",
            case_type="functional",
            created_by=admin.id,
            updated_by=admin.id,
        )
        case2 = TestCase(
            department_id=dept.id,
            title="数据导入",
            steps=[],
            keywords=[],
            priority="P2",
            case_type="functional",
            created_by=admin.id,
            updated_by=admin.id,
        )
        db.session.add_all([case1, case2])
        db.session.commit()

        return {
            "admin_id": admin.id,
            "tester_id": tester.id,
            "project_id": project.id,
            "device_ids": [device1.id, device2.id],
            "case_ids": [case1.id, case2.id],
        }


def test_plan_creation_and_execution_flow(app, seed_data):
    with app.app_context():
        admin = User.query.get(seed_data["admin_id"])
        tester = User.query.get(seed_data["tester_id"])
        project = Project.query.get(seed_data["project_id"])
        device1, device2 = [DeviceModel.query.get(i) for i in seed_data["device_ids"]]
        case1, case2 = [TestCase.query.get(i) for i in seed_data["case_ids"]]

        plan = TestPlanService.create(
            current_user=admin,
            project_id=project.id,
            name="版本迭代回归",
            description="覆盖核心流程",
            device_model_ids=[device1.id, device2.id],
            case_ids=[case1.id, case2.id],
            single_execution_case_ids=[case2.id],
            tester_user_ids=[tester.id],
        )

        assert plan.status == TestPlanStatus.PENDING.value
        assert len(plan.plan_cases) == 2
        case_map = {pc.case_id: pc for pc in plan.plan_cases}
        assert case_map[case1.id].require_all_devices is True
        assert case_map[case2.id].require_all_devices is False

        run = plan.execution_runs[0]
        assert run.total == 3  # case1 两个机型 + case2 单次
        assert run.not_run == 3

        # 第一次执行
        result1 = TestPlanService.record_result(
            plan.id,
            current_user=tester,
            plan_case_id=case_map[case1.id].id,
            device_model_id=device1.id,
            result=ExecutionResultStatus.PASS.value,
        )
        assert result1.result == ExecutionResultStatus.PASS.value

        refreshed = TestPlanService.get(plan.id)
        refreshed_run = refreshed.execution_runs[0]
        assert refreshed_run.executed == 1
        assert refreshed.status == TestPlanStatus.PENDING.value

        # 第二次执行（同用例不同机型）
        TestPlanService.record_result(
            plan.id,
            current_user=tester,
            plan_case_id=case_map[case1.id].id,
            device_model_id=device2.id,
            result=ExecutionResultStatus.FAIL.value,
            failure_reason="功能缺陷",
        )

        # 第三个结果（无需指定机型）
        TestPlanService.record_result(
            plan.id,
            current_user=tester,
            plan_case_id=case_map[case2.id].id,
            result=ExecutionResultStatus.BLOCK.value,
            remark="缺少测试数据",
        )

        completed = TestPlanService.get(plan.id)
        assert completed.status == TestPlanStatus.COMPLETED.value
        final_run = completed.execution_runs[0]
        assert final_run.executed == final_run.total == 3
        assert final_run.failed == 1
        assert final_run.blocked == 1

        # 归档并验证限制
        archived = TestPlanService.update(
            plan.id,
            current_user=admin,
            status=TestPlanStatus.ARCHIVED.value,
        )
        assert archived.status == TestPlanStatus.ARCHIVED.value

        with pytest.raises(BizError):
            TestPlanService.update(
                plan.id,
                current_user=admin,
                description="试图修改归档计划",
            )

        with pytest.raises(BizError):
            TestPlanService.delete(plan.id, current_user=admin)

        with pytest.raises(BizError):
            TestPlanService.record_result(
                plan.id,
                current_user=tester,
                plan_case_id=case_map[case2.id].id,
                result=ExecutionResultStatus.PASS.value,
            )
