from typing import Optional, Tuple, List
from sqlalchemy.exc import IntegrityError
from repositories.project_repository import ProjectRepository
from models.project import Project
from utils.exceptions import BizError
from constants.department_roles import DepartmentRole
from utils.permissions import PermissionScope, get_permission_scope


class ProjectService:

    @staticmethod
    def _require_scope(permission_scope: PermissionScope | None) -> PermissionScope:
        scope = permission_scope or get_permission_scope()
        if scope is None:
            raise BizError("权限校验失败（缺少权限范围）", code=500)
        return scope
    @staticmethod
    def create(
        department_id: int,
        name: str,
        code: Optional[str],
        description: Optional[str],
        owner_user_id: Optional[int],
        *,
        permission_scope: PermissionScope | None,
    ) -> Project:
        scope = ProjectService._require_scope(permission_scope)
        if not scope.has_department_role(department_id, DepartmentRole.ADMIN):
            raise BizError("无权限在该部门创建项目", 403)
        if not name:
            raise BizError("项目名称不能为空")
        if ProjectRepository.get_by_dept_and_name(department_id, name):
            raise BizError("项目名称已存在")
        if code and ProjectRepository.get_by_code(code):
            raise BizError("项目代码已存在")
        project = ProjectRepository.create(
            department_id=department_id,
            name=name,
            code=code,
            description=description,
            owner_user_id=owner_user_id,
            status="active",
        )
        try:
            ProjectRepository.commit()
        except IntegrityError:
            raise BizError("创建项目失败：唯一约束冲突")
        return project

    @staticmethod
    def get(project_id: int, *, permission_scope: PermissionScope | None) -> Project:
        scope = ProjectService._require_scope(permission_scope)
        proj = ProjectRepository.get_by_id(project_id)
        if not proj:
            raise BizError("项目不存在", code=404)
        if not scope.has_department_role(proj.department_id):
            raise BizError("无权访问该项目", 403)
        return proj

    @staticmethod
    def list(
        department_id: Optional[int] = None,
        name: Optional[str] = None,
        code: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        order_desc: bool = True,
        *,
        permission_scope: PermissionScope | None,
    ) -> Tuple[List[Project], int]:
        scope = ProjectService._require_scope(permission_scope)
        accessible_ids = scope.accessible_department_ids()
        if accessible_ids is not None:
            accessible_ids = list(accessible_ids)
        if department_id:
            if not scope.has_department_role(department_id):
                raise BizError("无权访问该部门项目", 403)
            if accessible_ids is None:
                accessible_ids = [department_id]
            else:
                if department_id not in accessible_ids:
                    return [], 0
                accessible_ids = [department_id]
        return ProjectRepository.list(
            department_id=department_id,
            name=name,
            code=code,
            status=status,
            page=page,
            page_size=page_size,
            order_desc=order_desc,
             accessible_department_ids=accessible_ids,
        )

    @staticmethod
    def update(
        project_id: int,
        name: Optional[str] = None,
        code: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        owner_user_id: Optional[int] = None,
        *,
        permission_scope: PermissionScope | None,
    ) -> Project:
        scope = ProjectService._require_scope(permission_scope)
        proj = ProjectService.get(project_id, permission_scope=scope)
        if not scope.has_department_role(proj.department_id, DepartmentRole.ADMIN):
            raise BizError("无权修改该项目", 403)
        if name:
            existing = ProjectRepository.get_by_dept_and_name(proj.department_id, name)
            if existing and existing.id != proj.id:
                raise BizError("项目名称已存在")
        if code:
            existing_code = ProjectRepository.get_by_code(code)
            if existing_code and existing_code.id != proj.id:
                raise BizError("项目代码已存在")
        ProjectRepository.update(
            proj,
            name=name,
            code=code,
            description=description,
            status=status,
            owner_user_id=owner_user_id,
        )
        try:
            ProjectRepository.commit()
        except IntegrityError:
            raise BizError("更新失败：唯一约束冲突")
        return proj

    @staticmethod
    def delete(project_id: int, user_id: Optional[int] = None, *, permission_scope: PermissionScope | None):
        scope = ProjectService._require_scope(permission_scope)
        proj = ProjectService.get(project_id, permission_scope=scope)
        if not scope.has_department_role(proj.department_id, DepartmentRole.ADMIN):
            raise BizError("无权删除该项目", 403)
        ProjectRepository.soft_delete(proj, user_id=user_id)
        ProjectRepository.commit()
