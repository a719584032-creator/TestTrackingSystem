from typing import List, Dict, Optional, Tuple, Iterable
from sqlalchemy import func, or_
from extensions.database import db
from models.case_group import CaseGroup
from models.test_case import TestCase


class CaseGroupRepository:

    @staticmethod
    def get_by_id(group_id: int, include_deleted: bool = False) -> Optional[CaseGroup]:
        q = CaseGroup.query
        if not include_deleted and hasattr(CaseGroup, "is_deleted"):
            q = q.filter(CaseGroup.is_deleted.is_(False))
        return q.filter(CaseGroup.id == group_id).first()

    @staticmethod
    def list_by_department(department_id: int, include_deleted: bool = False) -> List[CaseGroup]:
        q = CaseGroup.query.filter(CaseGroup.department_id == department_id)
        if not include_deleted and hasattr(CaseGroup, "is_deleted"):
            q = q.filter(CaseGroup.is_deleted.is_(False))
        return q.order_by(CaseGroup.parent_id.nullsfirst(), CaseGroup.order_no, CaseGroup.id).all()

    @staticmethod
    def list_children(department_id: int, parent_id: Optional[int], include_deleted: bool = False) -> List[CaseGroup]:
        q = CaseGroup.query.filter(
            CaseGroup.department_id == department_id,
            CaseGroup.parent_id == parent_id
        )
        if not include_deleted and hasattr(CaseGroup, "is_deleted"):
            q = q.filter(CaseGroup.is_deleted.is_(False))
        return q.order_by(CaseGroup.order_no, CaseGroup.id).all()

    @staticmethod
    def exists_name_under_parent(department_id: int, parent_id: Optional[int], name: str, exclude_id: Optional[int] = None) -> bool:
        q = CaseGroup.query.filter(
            CaseGroup.department_id == department_id,
            CaseGroup.parent_id == parent_id,
            CaseGroup.name == name
        )
        if exclude_id:
            q = q.filter(CaseGroup.id != exclude_id)
        if hasattr(CaseGroup, "is_deleted"):
            q = q.filter(CaseGroup.is_deleted.is_(False))
        return db.session.query(q.exists()).scalar()

    @staticmethod
    def create(**kwargs) -> CaseGroup:
        group = CaseGroup(**kwargs)
        db.session.add(group)
        return group

    @staticmethod
    def delete_groups_soft(group_ids: Iterable[int]):
        # 软删除（批量）
        if not group_ids:
            return 0
        q = CaseGroup.query.filter(CaseGroup.id.in_(group_ids))
        count = 0
        for g in q:
            if not getattr(g, "is_deleted", False):
                g.delete()  # SoftDeleteMixin
                count += 1
        return count

    @staticmethod
    def get_descendants(group: CaseGroup) -> List[CaseGroup]:
        # 利用 path 前缀匹配
        prefix = group.path + "/"
        q = CaseGroup.query.filter(
            CaseGroup.department_id == group.department_id,
            CaseGroup.path.like(f"{prefix}%")
        )
        if hasattr(CaseGroup, "is_deleted"):
            q = q.filter(CaseGroup.is_deleted.is_(False))
        return q.all()

    @staticmethod
    def get_descendant_ids_inclusive(group: CaseGroup) -> List[int]:
        descendants = CaseGroupRepository.get_descendants(group)
        ids = [group.id] + [g.id for g in descendants]
        return ids

    @staticmethod
    def update_group_parent_and_name(group: CaseGroup, new_parent: Optional[CaseGroup], new_name: Optional[str]):
        changed = False
        if new_parent is not None and group.parent_id != new_parent.id:
            group.parent_id = new_parent.id
            changed = True
        if new_parent is None and group.parent_id is not None:
            group.parent_id = None
            changed = True
        if new_name and group.name != new_name:
            group.name = new_name
            changed = True
        return changed

    @staticmethod
    def bulk_update_paths(updates: List[Tuple[int, str]]):
        """
        updates: list of (group_id, new_path)
        """
        for gid, np in updates:
            db.session.query(CaseGroup).filter(CaseGroup.id == gid).update({"path": np})

    @staticmethod
    def collect_test_case_ids_by_group_ids(group_ids: List[int]) -> List[int]:
        if not group_ids:
            return []
        q = TestCase.query.filter(TestCase.group_id.in_(group_ids))
        if hasattr(TestCase, "is_deleted"):
            q = q.filter(TestCase.is_deleted.is_(False))
        return [tc.id for tc in q]

    @staticmethod
    def count_cases_grouped(group_ids: List[int]) -> Dict[int, int]:
        if not group_ids:
            return {}
        q = db.session.query(
            TestCase.group_id,
            func.count(TestCase.id)
        ).filter(TestCase.group_id.in_(group_ids))
        if hasattr(TestCase, "is_deleted"):
            q = q.filter(TestCase.is_deleted.is_(False))
        q = q.group_by(TestCase.group_id)
        return {gid: cnt for gid, cnt in q.all()}


