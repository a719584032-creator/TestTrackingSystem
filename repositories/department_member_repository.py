# repositories/department_member_repository.py
from typing import Optional, List, Tuple, Dict
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from extensions.database import db
from models.department import DepartmentMember
from models.user import User


class DepartmentMemberRepository:

    @staticmethod
    def get_by_id(member_id: int) -> Optional[DepartmentMember]:
        return db.session.get(DepartmentMember, member_id)

    @staticmethod
    def get_by_dept_user(dept_id: int, user_id: int) -> Optional[DepartmentMember]:
        stmt = select(DepartmentMember).where(
            DepartmentMember.department_id == dept_id,
            DepartmentMember.user_id == user_id
        )
        return db.session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create(dept_id: int, user_id: int, role: str) -> DepartmentMember:
        m = DepartmentMember(department_id=dept_id, user_id=user_id, role=role)
        db.session.add(m)
        db.session.flush()
        return m

    @staticmethod
    def update_role(member: DepartmentMember, role: str) -> DepartmentMember:
        member.role = role
        db.session.flush()
        return member

    @staticmethod
    def delete(member: DepartmentMember):
        db.session.delete(member)

    @staticmethod
    def list(dept_id: int, keyword: Optional[str], role: Optional[str],
             page: int, page_size: int, order_by: str = "-id") -> Tuple[List[DepartmentMember], int]:
        stmt = select(DepartmentMember).where(DepartmentMember.department_id == dept_id).join(User)
        if role:
            stmt = stmt.where(DepartmentMember.role == role)
        if keyword:
            like = f"%{keyword.strip()}%"
            stmt = stmt.where(or_(User.username.ilike(like), User.email.ilike(like)))

        # 排序支持 user.username / id / role
        if order_by:
            desc = order_by.startswith("-")
            field = order_by[1:] if desc else order_by
            if field == "username":
                col = User.username
            else:
                col = getattr(DepartmentMember, field, None)
            if col is not None:
                stmt = stmt.order_by(col.desc() if desc else col.asc())
            else:
                stmt = stmt.order_by(DepartmentMember.id.desc())
        else:
            stmt = stmt.order_by(DepartmentMember.id.desc())

        total = db.session.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = db.session.execute(stmt).scalars().all()
        return rows, total

    @staticmethod
    def get_memberships_for_users(dept_id: int, user_ids: List[int]) -> Dict[int, DepartmentMember]:
        if not user_ids:
            return {}
        rows = (
            db.session.query(DepartmentMember)
            .filter(
                DepartmentMember.department_id == dept_id,
                DepartmentMember.user_id.in_(user_ids)
            )
            .all()
        )
        return {member.user_id: member for member in rows}

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
