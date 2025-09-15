from typing import Optional, List, Tuple
from sqlalchemy import select, func, desc, asc
from sqlalchemy.exc import IntegrityError
from extensions.database import db
from models.project import Project


class ProjectRepository:
    @staticmethod
    def create(department_id: int, name: str, code: Optional[str], description: Optional[str], owner_user_id: Optional[int], status: str = "active") -> Project:
        project = Project(
            department_id=department_id,
            name=name.strip(),
            code=code.strip() if code else None,
            description=description,
            owner_user_id=owner_user_id,
            status=status,
        )
        db.session.add(project)
        db.session.flush()
        return project

    @staticmethod
    def get_by_id(project_id: int) -> Optional[Project]:
        return db.session.get(Project, project_id)

    @staticmethod
    def get_by_dept_and_name(department_id: int, name: str) -> Optional[Project]:
        stmt = select(Project).where(Project.department_id == department_id, Project.name == name)
        return db.session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_code(code: str) -> Optional[Project]:
        stmt = select(Project).where(Project.code == code)
        return db.session.execute(stmt).scalar_one_or_none()

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
        stmt = select(Project)
        count_stmt = select(func.count(Project.id))
        conditions = []
        if department_id:
            conditions.append(Project.department_id == department_id)
        if name:
            conditions.append(Project.name.ilike(f"%{name.strip()}%"))
        if code:
            conditions.append(Project.code.ilike(f"%{code.strip()}%"))
        if status:
            conditions.append(Project.status == status)
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)
        if order_desc:
            stmt = stmt.order_by(desc(Project.created_at))
        else:
            stmt = stmt.order_by(asc(Project.created_at))
        total = db.session.execute(count_stmt).scalar()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = db.session.execute(stmt).scalars().all()
        return items, total

    @staticmethod
    def update(project: Project, name: Optional[str] = None, code: Optional[str] = None, description: Optional[str] = None, status: Optional[str] = None, owner_user_id: Optional[int] = None) -> Project:
        if name is not None:
            project.name = name.strip()
        if code is not None:
            project.code = code.strip() if code else None
        if description is not None:
            project.description = description
        if status is not None:
            project.status = status
        if owner_user_id is not None:
            project.owner_user_id = owner_user_id
        db.session.flush()
        return project

    @staticmethod
    def delete(project: Project):
        db.session.delete(project)
        db.session.flush()

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
