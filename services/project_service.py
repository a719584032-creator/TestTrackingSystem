from typing import Optional, Tuple, List
from sqlalchemy.exc import IntegrityError
from repositories.project_repository import ProjectRepository
from models.project import Project
from utils.exceptions import BizError


class ProjectService:
    @staticmethod
    def create(department_id: int, name: str, code: Optional[str], description: Optional[str], owner_user_id: Optional[int]) -> Project:
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
    def get(project_id: int) -> Project:
        proj = ProjectRepository.get_by_id(project_id)
        if not proj:
            raise BizError("项目不存在", code=404)
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
    ) -> Tuple[List[Project], int]:
        return ProjectRepository.list(
            department_id=department_id,
            name=name,
            code=code,
            status=status,
            page=page,
            page_size=page_size,
            order_desc=order_desc,
        )

    @staticmethod
    def update(
        project_id: int,
        name: Optional[str] = None,
        code: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        owner_user_id: Optional[int] = None,
    ) -> Project:
        proj = ProjectService.get(project_id)
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
    def delete(project_id: int):
        proj = ProjectService.get(project_id)
        ProjectRepository.delete(proj)
        ProjectRepository.commit()
