# services/department_member_service.py
from typing import Optional, List, Tuple
from sqlalchemy.exc import IntegrityError
from repositories.department_member_repository import DepartmentMemberRepository
from repositories.department_repository import DepartmentRepository
from repositories.user_repository import UserRepository
from utils.exceptions import BizError
from constants.department_roles import DEPARTMENT_ROLE_SET


class DepartmentMemberService:

    @staticmethod
    def add_member(dept_id: int, user_id: int, role: str, upsert: bool = False):
        dept = DepartmentRepository.get_by_id(dept_id)
        if not dept:
            raise BizError("部门不存在", 404)
        if not dept.active:
            raise BizError("部门已被禁用", 403)
        user = UserRepository.find_by_id(user_id)
        if not user:
            raise BizError("用户不存在", 404)

        if role not in DEPARTMENT_ROLE_SET:
            raise BizError("非法部门角色")

        existing = DepartmentMemberRepository.get_by_dept_user(dept_id, user_id)
        if existing:
            if upsert:
                existing.role = role
                DepartmentMemberRepository.commit()
                return existing, True  # True 表示更新
            else:
                raise BizError("成员已存在")
        m = DepartmentMemberRepository.create(dept_id=dept_id, user_id=user_id, role=role)
        DepartmentMemberRepository.commit()
        return m, False

    @staticmethod
    def update_member_role(member_id: int, role: str):
        if role not in DEPARTMENT_ROLE_SET:
            raise BizError("非法部门角色")
        member = DepartmentMemberRepository.get_by_id(member_id)
        if not member:
            raise BizError("成员关系不存在", 404)
        DepartmentMemberRepository.update_role(member, role)
        DepartmentMemberRepository.commit()
        return member

    @staticmethod
    def remove_by_dept_user(dept_id: int, user_id: int):
        member = DepartmentMemberRepository.get_by_dept_user(dept_id, user_id)
        if not member:
            return False
        DepartmentMemberRepository.delete(member)
        DepartmentMemberRepository.commit()
        return True

    @staticmethod
    def list_members(dept_id: int, keyword: Optional[str], role: Optional[str],
                     page: int, page_size: int, order_by: str):
        dept = DepartmentRepository.get_by_id(dept_id)
        if not dept:
            raise BizError("部门不存在", 404)
        if not dept.active:
            raise BizError("部门已被禁用", 403)
        if role and role not in DEPARTMENT_ROLE_SET:
            raise BizError("非法角色过滤值")
        return DepartmentMemberRepository.list(
            dept_id=dept_id,
            keyword=keyword,
            role=role,
            page=page,
            page_size=page_size,
            order_by=order_by
        )
