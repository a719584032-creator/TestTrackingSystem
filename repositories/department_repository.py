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
             order_desc: bool = True) -> Tuple[List[Department], int, Dict]:
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

        # 一次查询获取所有计数
        count_query = db.session.query(
            Department.id,
            func.count(DepartmentMember.id).label('members_count'),
            func.count(Project.id).label('projects_count'),
            func.count(TestCase.id).label('test_cases_count'),
            func.count(DeviceModel.id).label('device_models_count')
        ).select_from(Department) \
            .outerjoin(DepartmentMember, Department.id == DepartmentMember.department_id) \
            .outerjoin(Project, Department.id == Project.department_id) \
            .outerjoin(TestCase, Department.id == TestCase.department_id) \
            .outerjoin(DeviceModel, Department.id == DeviceModel.department_id) \
            .filter(Department.id.in_(dept_ids)) \
            .group_by(Department.id)

        results = count_query.all()

        counts_data = {}
        for result in results:
            counts_data[result.id] = {
                "members": result.members_count or 0,
                "projects": result.projects_count or 0,
                "test_cases": result.test_cases_count or 0,
                "device_models": result.device_models_count or 0,
            }

        # 确保所有部门都有计数数据
        for dept_id in dept_ids:
            if dept_id not in counts_data:
                counts_data[dept_id] = {
                    "members": 0,
                    "projects": 0,
                    "test_cases": 0,
                    "device_models": 0,
                }

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
