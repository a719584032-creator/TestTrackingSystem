# repositories/department_repository.py
from typing import Optional, List, Tuple
from sqlalchemy import select, func, or_, case, desc, asc
from sqlalchemy.exc import IntegrityError
from extensions.database import db
from models.department import Department
from sqlalchemy.orm import selectinload
from typing import Optional, Tuple, List, Dict
from models.department import Department, DepartmentMember
from models.project import Project
from models.test_case import TestCase
from models.device_model import DeviceModel


class DepartmentRepository:

    @staticmethod
    def create(name: str, code: Optional[str], description: Optional[str], active: bool = True) -> Department:
        dept = Department(name=name.strip(), code=code.strip() if code else None,
                          description=description, active=active)
        db.session.add(dept)
        db.session.flush()
        return dept

    @staticmethod
    def get_by_id(dept_id: int) -> Optional[Department]:
        return db.session.get(Department, dept_id)

    @staticmethod
    def get_by_name(name: str) -> Optional[Department]:
        stmt = select(Department).where(Department.name == name)
        return db.session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_code(code: str) -> Optional[Department]:
        stmt = select(Department).where(Department.code == code)
        return db.session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list(name: Optional[str] = None,
             code: Optional[str] = None,
             active: Optional[bool] = None,
             page: int = 1,
             page_size: int = 20,
             order_desc: bool = True,
             accessible_user_id: Optional[int] = None) -> Tuple[List[Department], int, Dict]:
        """
        优化的部门列表查询
        :param name: 部门名称（模糊匹配）
        :param code: 部门编码（模糊匹配）
        :param active: 部门状态
        :param page: 页码
        :param page_size: 每页大小
        :param order_desc: 是否按创建时间倒序
        :return: (部门列表, 总数, 计数数据)
        """
        # 构建基础查询
        stmt = select(Department)
        count_stmt = select(func.count(Department.id))

        # 构建筛选条件
        conditions = []

        # 用户可见范围限制
        if accessible_user_id:
            subq = (
                select(DepartmentMember.department_id)
                .where(DepartmentMember.user_id == accessible_user_id)
            )
            stmt = stmt.where(Department.id.in_(subq))
            count_stmt = count_stmt.where(Department.id.in_(subq))

        if name:
            conditions.append(Department.name.ilike(f"%{name.strip()}%"))

        if code:
            conditions.append(Department.code.ilike(f"%{code.strip()}%"))

        if active is not None:
            conditions.append(Department.active == active)

        # 应用筛选条件
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        # 排序
        if order_desc:
            stmt = stmt.order_by(desc(Department.created_at))
        else:
            stmt = stmt.order_by(asc(Department.created_at))

        # 获取总数
        total = db.session.execute(count_stmt).scalar()

        # 分页查询
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        departments = db.session.execute(stmt).scalars().all()

        # 批量获取计数数据（关键优化点）
        counts_data = {}
        if departments:
            dept_ids = [d.id for d in departments]
            counts_data = DepartmentRepository._get_batch_counts(dept_ids)

        return departments, total, counts_data

    @staticmethod
    def _get_batch_counts(dept_ids: List[int]) -> Dict[int, Dict]:
        """批量获取部门的统计数据，避免N+1查询"""
        if not dept_ids:
            return {}

        # 初始化结果，避免在后续更新前访问不存在的键
        counts_data = {
            dept_id: {
                "members": 0,
                "projects": 0,
                "test_cases": 0,
                "device_models": 0,
            }
            for dept_id in dept_ids
        }

        def _apply_counts(query, key: str):
            for dept_id, value in query:
                counts_data[dept_id][key] = value or 0

        # 分别统计，避免一次性 JOIN 导致的行数爆炸
        members_query = (
            db.session.query(
                DepartmentMember.department_id,
                func.count(DepartmentMember.id)
            )
            .filter(DepartmentMember.department_id.in_(dept_ids))
            .group_by(DepartmentMember.department_id)
        )
        _apply_counts(members_query.all(), "members")

        projects_query = (
            db.session.query(
                Project.department_id,
                func.count(Project.id)
            )
            .filter(Project.department_id.in_(dept_ids))
            .group_by(Project.department_id)
        )
        _apply_counts(projects_query.all(), "projects")

        test_cases_query = (
            db.session.query(
                TestCase.department_id,
                func.count(TestCase.id)
            )
            .filter(TestCase.department_id.in_(dept_ids))
            .group_by(TestCase.department_id)
        )
        _apply_counts(test_cases_query.all(), "test_cases")

        device_models_query = (
            db.session.query(
                DeviceModel.department_id,
                func.sum(
                    case((DeviceModel.active == True, 1), else_=0)  # noqa: E712
                ),
            )
            .filter(DeviceModel.department_id.in_(dept_ids))
            .group_by(DeviceModel.department_id)
        )
        _apply_counts(device_models_query.all(), "device_models")

        return counts_data

    @staticmethod
    def update(dept: Department, name: Optional[str], code: Optional[str],
               description: Optional[str], active: Optional[bool]) -> Department:
        if name is not None:
            dept.name = name.strip()
        if code is not None:
            dept.code = code.strip() if code else None
        if description is not None:
            dept.description = description
        if active is not None:
            dept.active = active
        db.session.flush()
        return dept

    @staticmethod
    def update_status(dept: Department, active: bool):
        """更新部门状态"""
        dept.active = active
        db.session.flush()

    @staticmethod
    def count_active_members(dept_id: int) -> int:
        """统计部门的成员数量"""
        return db.session.query(DepartmentMember).filter(
            DepartmentMember.department_id == dept_id
        ).count()

    @staticmethod
    def count_active_projects(dept_id: int) -> int:
        """统计部门的项目数量"""
        return db.session.query(Project).filter(
            Project.department_id == dept_id,
        ).count()


    @staticmethod
    def commit():
        try:
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            raise e

    @staticmethod
    def rollback():
        db.session.rollback()
