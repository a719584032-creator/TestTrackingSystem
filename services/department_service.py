# services/department_service.py
from typing import Optional, Tuple, List, Dict
from sqlalchemy.exc import IntegrityError
from repositories.department_repository import DepartmentRepository
from models.department import Department
from utils.exceptions import BizError
from utils.permissions import PermissionScope
import logging

logger = logging.getLogger(__name__)


class DepartmentService:

    @staticmethod
    def create(name: str, code: Optional[str], description: Optional[str]):

        if not name:
            raise BizError("部门名称不能为空")

        if DepartmentRepository.get_by_name(name):
            raise BizError("部门名称已存在")

        if code and DepartmentRepository.get_by_code(code):
            raise BizError("部门代码已存在")

        dept = DepartmentRepository.create(name=name, code=code, description=description, active=True)
        try:
            DepartmentRepository.commit()
        except IntegrityError as e:
            raise BizError("创建部门失败：唯一约束冲突")
        return dept

    @staticmethod
    def get(dept_id: int):
        dept = DepartmentRepository.get_by_id(dept_id)
        if not dept:
            raise BizError("部门不存在", code=404)
        # if not dept.active:
        #     raise BizError("部门已被禁用", code=403)
        return dept

    @staticmethod
    def list(name: Optional[str] = None,
             code: Optional[str] = None,
             active: Optional[bool] = None,  # 保留签名兼容（忽略）
             page: int = 1,
             page_size: int = 20,
             order_desc: bool = True,
             permission_scope: PermissionScope | None = None) -> Tuple[List[Department], int, Dict]:
        """
        部门列表查询
        :param name: 部门名称
        :param code: 部门编码
        :param active: 部门状态
        :param page: 页码
        :param page_size: 每页大小
        :param order_desc: 是否按创建时间倒序
        """
        accessible_ids = None
        if permission_scope:
            accessible_ids = permission_scope.accessible_department_ids()
            if accessible_ids is not None:
                accessible_ids = list(accessible_ids)
        return DepartmentRepository.list(
            name=name,
            code=code,
            active=active,
            page=page,
            page_size=page_size,
            order_desc=order_desc,
            accessible_department_ids=accessible_ids
        )

    @staticmethod
    def update(dept_id: int, name: Optional[str], code: Optional[str],
               description: Optional[str], active: Optional[bool]):
        dept = DepartmentService.get(dept_id)

        if name:
            existing = DepartmentRepository.get_by_name(name)
            if existing and existing.id != dept.id:
                raise BizError("部门名称已存在")

        if code:
            existing_code = DepartmentRepository.get_by_code(code)
            if existing_code and existing_code.id != dept.id:
                raise BizError("部门代码已存在")

        DepartmentRepository.update(dept, name=name, code=code,
                                    description=description, active=active)
        try:
            DepartmentRepository.commit()
        except IntegrityError:
            raise BizError("更新失败：唯一约束冲突")
        return dept

    @staticmethod
    def toggle_status(dept_id: int, active: bool):
        """切换部门状态"""
        dept = DepartmentService.get(dept_id)

        # 检查是否可以禁用部门
        if not active:
            # 检查是否有活跃的成员
            active_members_count = DepartmentRepository.count_active_members(dept_id)
            if active_members_count > 0:
                raise ValueError(f"无法禁用部门，该部门还有 {active_members_count} 个活跃成员")

            # 检查是否有活跃的项目
            # active_projects_count = DepartmentRepository.count_active_projects(dept_id)
            # if active_projects_count > 0:
            #     raise ValueError(f"无法禁用部门，该部门还有 {active_projects_count} 个活跃项目")

        DepartmentRepository.update_status(dept, active=active)
        DepartmentRepository.commit()

        return dept
