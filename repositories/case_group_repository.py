from typing import List, Dict, Optional, Tuple, Iterable
from sqlalchemy import func, and_, or_, desc, asc
from extensions.database import db
from models.case_group import CaseGroup
from models.test_case import TestCase
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


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
        return q.order_by(
            (CaseGroup.parent_id.is_(None)).desc(),  # 先把 NULL 放前面
            CaseGroup.order_no,
            CaseGroup.id
        ).all()

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
    def exists_name_under_parent(department_id: int, parent_id: Optional[int], name: str,
                                 exclude_id: Optional[int] = None) -> bool:
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
        db.session.flush()  # 确保能生成 group.id
        return group

    @staticmethod
    def delete_groups_soft(group_ids: Iterable[int], department_id: int, user_id: int) -> int:
        """批量软删除分组"""
        if not group_ids:
            return 0
        affected = CaseGroup.query.filter(
            and_(
                CaseGroup.id.in_(group_ids),
                CaseGroup.department_id == department_id,
                CaseGroup.is_deleted == False
            )
        ).update(
            {
                "is_deleted": True,
                "deleted_at": datetime.utcnow(),
                "deleted_by": user_id
            },
            synchronize_session=False
        )
        db.session.commit()
        return affected

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
    def get_descendants_by_path_prefix(department_id: int, old_path: str) -> List[CaseGroup]:
        prefix = old_path + "/"
        q = CaseGroup.query.filter(
            CaseGroup.department_id == department_id,
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
    def update_group_parent_and_name(group: CaseGroup, new_parent: Optional[CaseGroup], new_name: Optional[str],
                                     update_parent: bool):
        changed = False

        if update_parent:  # 只有显式传了 parent_id 才更新父节点
            if new_parent is not None and group.parent_id != new_parent.id:
                group.parent_id = new_parent.id
                changed = True
            if new_parent is None and group.parent_id is not None:
                group.parent_id = None
                changed = True

        if new_name and group.name != new_name:
            logger.debug(f'new_name is {new_name}')
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
